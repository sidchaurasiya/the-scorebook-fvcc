"""Isolated control-model tests; never imports app code or contacts production.

These prove the proposed control model and Git recovery method, not a finished
production workflow or a provisioned remote state store.
"""
import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ORDER = ['GRDCC', 'GWHCC', 'FVCC']
ZONE = ZoneInfo('Australia/Melbourne')


def atomic(path, value):
    temporary = path.with_suffix('.new')
    with open(temporary, 'w') as handle:
        json.dump(value, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class Model:
    def __init__(self, root):
        self.path = root / 'state.json'
        self.state = json.loads(self.path.read_text()) if self.path.exists() else {
            'lock_owner': None, 'completed': {}, 'push_intent': None, 'push_attempts': 0,
            'clubs': {club: {'published': 'known-good', 'quarantine': []} for club in ORDER}}

    def save(self):
        atomic(self.path, self.state)

    def acquire(self, owner, owner_status):
        old = self.state['lock_owner']
        if old and old != owner and owner_status(old) != 'completed':
            raise RuntimeError('owner still active or status unknown')
        self.state['lock_owner'] = owner
        self.save()

    def check(self, slot, categories, interrupt_after=None):
        visits, heavy = [], []
        completed = self.state['completed'].setdefault(slot, {})
        for club in ORDER:
            visits.append(club)
            if club in completed:
                continue
            category = categories.get(club, 'E')
            if category == 'F':
                self.state['clubs'][club]['quarantine'].append('ambiguous-payload')
            if category in {'A', 'B'}:
                heavy.append(club)
            completed[club] = {'category': category, 'requires_validation': category in {'A', 'B'}}
            self.save()
            if club == interrupt_after:
                raise InterruptedError('simulated termination after durable checkpoint')
        return visits, heavy

    def publish(self, candidate, observed_remote, validations, send):
        if observed_remote == candidate:
            self.state['push_intent'] = {'candidate': candidate, 'status': 'published-observed'}
            self.save()
            return 'already-published'
        if self.state['push_attempts']:
            raise RuntimeError('uncertain or failed push requires review; never automatic retry')
        if observed_remote != 'base' or not validations or not all(validations):
            raise RuntimeError('obsolete ancestry or failed validation')
        self.state['push_intent'] = {'candidate': candidate, 'status': 'attempting'}
        self.state['push_attempts'] += 1
        self.save()
        send()
        self.state['push_intent']['status'] = 'response-received'
        self.save()


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='scorebook-simulation-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.model = Model(self.root)

    def test_all_trigger_types_share_order_and_unchanged_skip(self):
        for slot in ['saturday-1800', 'sunday-1800', 'monday-1300']:
            visits, heavy = self.model.check(slot, {})
            self.assertEqual(visits, ORDER)
            self.assertEqual(heavy, [])
        self.assertEqual(self.model.state['push_attempts'], 0)

    def test_one_and_multiple_club_validation_gates(self):
        self.assertEqual(self.model.check('one', {'GWHCC': 'A'})[1], ['GWHCC'])
        self.assertEqual(self.model.check('many', {'GRDCC': 'B', 'FVCC': 'A'})[1], ['GRDCC', 'FVCC'])
        with self.assertRaises(RuntimeError):
            self.model.publish('candidate', 'base', [True, False], lambda: self.fail('unsafe push'))

    def test_provisional_and_metadata_changes_skip_heavy_work(self):
        self.assertEqual(self.model.check('skip', {'GRDCC': 'C', 'GWHCC': 'D', 'FVCC': 'E'})[1], [])

    def test_ambiguity_quarantines_and_later_clubs_are_visited(self):
        visits, heavy = self.model.check('ambiguous', {'GRDCC': 'F', 'FVCC': 'A'})
        self.assertEqual(visits, ORDER)
        self.assertEqual(heavy, ['FVCC'])
        self.assertEqual(self.model.state['clubs']['GRDCC']['quarantine'], ['ambiguous-payload'])

    def test_interrupt_recovers_checkpoint_without_repeating_work(self):
        with self.assertRaises(InterruptedError):
            self.model.check('resume', {'GRDCC': 'A', 'FVCC': 'B'}, interrupt_after='GRDCC')
        recovered = Model(self.root)
        self.assertEqual(recovered.check('resume', {'GRDCC': 'A', 'FVCC': 'B'}), (ORDER, ['FVCC']))
        self.assertEqual(recovered.check('resume', {'GRDCC': 'A', 'FVCC': 'B'}), (ORDER, []))

    def test_shared_lock_rejects_active_and_unverifiable_owners(self):
        self.model.acquire('saturday', lambda _: 'completed')
        for status in ['in_progress', 'unknown']:
            with self.assertRaises(RuntimeError):
                self.model.acquire('sunday', lambda _: status)
        self.model.acquire('sunday', lambda _: 'completed')
        self.assertEqual(Model(self.root).state['lock_owner'], 'sunday')

    def test_push_response_loss_is_reconciled_without_repeat(self):
        def lost_response():
            raise ConnectionError('remote accepted; response lost')
        with self.assertRaises(ConnectionError):
            self.model.publish('candidate', 'base', [True], lost_response)
        recovered = Model(self.root)
        self.assertEqual(recovered.publish('candidate', 'candidate', [True], lambda: self.fail('duplicate')), 'already-published')
        self.assertEqual(recovered.state['push_attempts'], 1)

    def test_failed_push_is_never_automatically_retried(self):
        def rejection():
            raise ConnectionError('rejected')
        with self.assertRaises(ConnectionError):
            self.model.publish('candidate', 'base', [True], rejection)
        with self.assertRaises(RuntimeError):
            Model(self.root).publish('candidate', 'base', [True], lambda: self.fail('retry'))

    def test_concurrent_main_advance_blocks_publication(self):
        with self.assertRaises(RuntimeError):
            self.model.publish('candidate', 'other-commit', [True], lambda: self.fail('overwrite'))

    def test_runtime_delay_does_not_allow_rollback(self):
        def rollback_allowed(cause, isolated, unchanged_remote):
            return cause in {'critical-data-corruption', 'critical-identity-exposure', 'release-caused-startup-failure'} and isolated and unchanged_remote
        for cause in ['stale-footer', 'worker-delayed', 'cpu-throttling', 'build-in-progress']:
            self.assertFalse(rollback_allowed(cause, True, True))
        self.assertTrue(rollback_allowed('critical-data-corruption', True, True))
        self.assertFalse(rollback_allowed('critical-data-corruption', False, True))

    def test_both_dst_transitions_preserve_local_hours(self):
        expected = {'2027-04-03T18:00': 7, '2027-04-04T18:00': 8, '2027-04-05T13:00': 3,
                    '2027-10-02T18:00': 8, '2027-10-03T18:00': 7, '2027-10-04T13:00': 2}
        for local, utc_hour in expected.items():
            moment = datetime.fromisoformat(local).replace(tzinfo=ZONE)
            self.assertEqual(moment.astimezone(timezone.utc).hour, utc_hour)
            self.assertEqual(moment.astimezone(timezone.utc).astimezone(ZONE), moment)

    def test_monday_weekend_key_is_preceding_saturday(self):
        for text in ['2026-10-24T18:00', '2026-10-25T18:00', '2026-10-26T13:00']:
            local = datetime.fromisoformat(text).replace(tzinfo=ZONE)
            saturday = local.date() - timedelta(days=(local.weekday() - 5) % 7)
            self.assertEqual(str(saturday), '2026-10-24')

    def test_real_non_fast_forward_push_is_rejected_without_retry(self):
        def git(path, *args, check=True):
            return subprocess.run(['git', *args], cwd=path, check=check, capture_output=True, text=True)
        remote = self.root / 'conflict.git'
        git(self.root, 'init', '--bare', str(remote))
        writer = self.root / 'first-writer'
        git(self.root, 'clone', str(remote), str(writer))
        git(writer, 'config', 'user.name', 'Simulation')
        git(writer, 'config', 'user.email', 'simulation@example.invalid')
        git(writer, 'checkout', '-b', 'main')
        (writer / 'synthetic.txt').write_text('base\n')
        git(writer, 'add', 'synthetic.txt')
        git(writer, 'commit', '-m', 'base')
        git(writer, 'push', 'origin', 'main')
        stale = self.root / 'stale-writer'
        git(self.root, 'clone', '--branch', 'main', str(remote), str(stale))
        git(stale, 'config', 'user.name', 'Simulation')
        git(stale, 'config', 'user.email', 'simulation@example.invalid')
        (writer / 'synthetic.txt').write_text('concurrent release\n')
        git(writer, 'add', 'synthetic.txt')
        git(writer, 'commit', '-m', 'concurrent advance')
        git(writer, 'push', 'origin', 'main')
        expected = git(writer, 'rev-parse', 'HEAD').stdout.strip()
        (stale / 'synthetic.txt').write_text('obsolete candidate\n')
        git(stale, 'add', 'synthetic.txt')
        git(stale, 'commit', '-m', 'obsolete candidate')
        rejected = git(stale, 'push', 'origin', 'HEAD:main', check=False)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(git(stale, 'ls-remote', 'origin', 'refs/heads/main').stdout.split()[0], expected)

    def test_real_git_revert_preserves_other_clubs_and_quarantines(self):
        def git(path, *args, check=True):
            return subprocess.run(['git', *args], cwd=path, check=check, capture_output=True, text=True)
        remote = self.root / 'remote.git'
        git(self.root, 'init', '--bare', str(remote))
        local = self.root / 'writer'
        git(self.root, 'clone', str(remote), str(local))
        git(local, 'config', 'user.name', 'Scorebook simulation')
        git(local, 'config', 'user.email', 'simulation@example.invalid')
        git(local, 'checkout', '-b', 'main')
        for club in ORDER:
            path = local / f'clubs/{club}/data/synthetic.txt'
            path.parent.mkdir(parents=True)
            path.write_text('known-good\n')
        git(local, 'add', 'clubs')
        git(local, 'commit', '-m', 'synthetic baseline')
        git(local, 'push', 'origin', 'main')
        base = git(local, 'rev-parse', 'HEAD').stdout.strip()
        commits = {}
        for club in ORDER:
            path = local / f'clubs/{club}/data/synthetic.txt'
            path.write_text('candidate\n')
            git(local, 'add', str(path.relative_to(local)))
            git(local, 'commit', '-m', f'synthetic data {club}')
            commits[club] = git(local, 'rev-parse', 'HEAD').stdout.strip()
        git(local, 'push', 'origin', 'HEAD:main')
        bad = git(local, 'rev-parse', 'HEAD').stdout.strip()
        observed = git(local, 'ls-remote', 'origin', 'refs/heads/main').stdout.split()[0]
        self.assertEqual(observed, bad)
        git(local, 'revert', '--no-edit', commits['GRDCC'])
        self.assertEqual((local / 'clubs/GRDCC/data/synthetic.txt').read_text(), 'known-good\n')
        for club in ['GWHCC', 'FVCC']:
            self.assertEqual((local / f'clubs/{club}/data/synthetic.txt').read_text(), 'candidate\n')
        affected = git(local, 'diff-tree', '--no-commit-id', '--name-only', '-r', 'HEAD').stdout.splitlines()
        self.assertEqual(affected, ['clubs/GRDCC/data/synthetic.txt'])
        git(local, 'push', 'origin', 'HEAD:main')
        rollback = git(local, 'rev-parse', 'HEAD').stdout.strip()
        self.assertEqual(git(local, 'ls-remote', 'origin', 'refs/heads/main').stdout.split()[0], rollback)
        self.model.state['clubs']['GRDCC']['quarantine'].append('synthetic-bad-payload')
        self.model.save()
        self.assertIn('synthetic-bad-payload', Model(self.root).state['clubs']['GRDCC']['quarantine'])
        # Persist checkpoint into a separate Git state branch, then recover into
        # a fresh checkout, modeling replacement of the entire runner filesystem.
        (local / 'state.json').write_bytes(self.model.path.read_bytes())
        git(local, 'checkout', '-b', 'simulation-state')
        git(local, 'add', 'state.json')
        git(local, 'commit', '-m', 'synthetic durable state')
        git(local, 'push', 'origin', 'simulation-state')
        fresh = self.root / 'new-runner'
        git(self.root, 'clone', '--branch', 'simulation-state', str(remote), str(fresh))
        self.assertEqual(json.loads((fresh / 'state.json').read_text()), self.model.state)
        receipt = {'baseline': base, 'bad_release': bad, 'rollback': rollback,
                   'affected_paths': affected, 'other_clubs_preserved': True,
                   'production_touched': False, 'state_recovered_from_git': True}
        self.assertNotEqual(base, rollback)
        print('SIMULATED_ROLLBACK ' + json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    unittest.main(verbosity=2)
