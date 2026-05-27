# Multi-Club Fastest Innings Audit

Generated after rebuilding deploy-safe outputs from existing local match-centre and ball-by-ball data. No fetch/backfill was run.

## Validation Rules

- Fastest innings records use verified local ball-by-ball rows only.
- Batter runs now come from per-delivery `runs_bat` progression unless source cumulative runs validate cleanly.
- Source cumulative run fields are treated as advisory because some rows jump to final scores early or move backward.
- Scorecard balls of `0` are treated as missing when verified legal ball counts exist.
- Fastest 50s below 9 balls and fastest 100s below 17 balls are excluded unless explicitly verified by a trustworthy delivery sequence.

## Pre-Fix Suspicious Rows

| club_id | player | milestone | pre-fix balls | final score | match_id | post-fix status |
|---|---:|---:|---:|---:|---|---|
| plenty | Geoffrey King | 50 | 6 | 59* | `f14f0307-92ab-405d-b6d8-1fc79a520909` | fixed to 52 balls from per-delivery batter runs |
| reynella | Cameron Pannach | 50 | 3 | 65 | `637c5cda-d515-4c80-a007-dff096b9ccb0` | fixed to 63 balls from per-delivery batter runs |
| georges-river-district | Christopher McArthur | 50 | 1 | 95 | `7bb574ec-037a-4c18-9487-1bcd5906afcb` | fixed to 35 balls from per-delivery batter runs |

## Club Results

### Southside East Caulfield

- Deploy-safe rows: 415 before, 390 after.
- Post-fix rows under hard threshold: 0.
- Validation exclusions in local milestone builder: 53.
- Invalid source cumulative run warnings: 11.
- Result: no impossible fastest 50/100 rows remain in deploy-safe output.

**Top validated fastest 50s**

- Vamsee Gujjalapudi: 20 balls, 54*, Summer 2022/23, `edb4c5f1-8ff1-4419-bb99-7e9923490406`
- Pratikkumar Patel: 22 balls, 50*, Summer 2025/26, `6bffed5a-318e-4f68-b933-bcc6564be428`
- Jatin Dave: 23 balls, 52*, Summer 2024/25, `16abf8a3-b6d5-4d12-898c-ddba24dcabc5`
- Mehul Tandel: 25 balls, 50*, Summer 2025/26, `1ab342c2-b910-44e1-a4f1-c04558a5714e`
- Sherwin Lobo: 26 balls, 50*, Winter 2026, `ae277c92-c448-4083-8089-f4a7ea86380a`

**Top validated fastest 100s**

- Skander Munir: 73 balls, 106, Summer 2024/25, `2d79ea3e-34fd-44d3-bb23-d70618406011`
- Puneet Bhardwaj: 75 balls, 101, Summer 2020/21, `192d30e3-13e2-43a9-ba73-7dec8a2c78a4`
- Siddhant Tirodkar: 79 balls, 118, Summer 2025/26, `51a0d287-a007-4bea-8ae7-80a05e519182`
- Aamir Rana: 95 balls, 130*, Summer 2025/26, `6a04c985-85ad-4b04-9dcb-5ab4c8c0664b`
- Shyam Kikani: 107 balls, 110, Summer 2019/20, `917c0742-1ceb-4322-a48d-8a6e5ce64aa9`

### Glen Waverley Hawks

- Deploy-safe rows: 784 before, 730 after.
- Post-fix rows under hard threshold: 0.
- Validation exclusions in local milestone builder: 257.
- Invalid source cumulative run warnings: 17.
- Result: no impossible fastest 50/100 rows remain in deploy-safe output.

**Top validated fastest 50s**

- Pravin Chelvan: 19 balls, 73, Summer 2023/24, `256a7613-0b9b-4610-ad9d-a22242ee55fe`
- Paul Young: 21 balls, 108*, Summer 2022/23, `41056ac5-171f-4bb7-a0a5-576084285f88`
- Tushar Pai: 22 balls, 59, Summer 2016/17, `4c2ca82a-a39d-4904-a122-3b532617a86b`
- Arun Chelvan: 24 balls, 66, Summer 2023/24, `18dd08e0-c1cf-40b2-b097-1cbb7ac9453f`
- Simon Gordon: 25 balls, 94, Summer 2022/23, `70860192-38ff-41b8-985f-4bcc25fb99df`

**Top validated fastest 100s**

- Paul Young: 34 balls, 108*, Summer 2022/23, `41056ac5-171f-4bb7-a0a5-576084285f88`
- Paul Young: 54 balls, 116*, Summer 2022/23, `acdb94d8-9b63-4245-b1cb-e888ad183733`
- Brett Powell: 74 balls, 105, Summer 2016/17, `4c2ca82a-a39d-4904-a122-3b532617a86b`
- Paul Young: 77 balls, 118*, Summer 2023/24, `5e01e175-a06b-4dea-af26-956deccb2f2b`
- Karanvir Singh: 84 balls, 132, Summer 2023/24, `53e0f57f-a6ae-48cb-b79c-f4f227616bb1`

### Ashwood

- Deploy-safe rows: 1,019 before, 940 after.
- Post-fix rows under hard threshold: 0.
- Validation exclusions in local milestone builder: 382.
- Invalid source cumulative run warnings: 30.
- Result: no impossible fastest 50/100 rows remain in deploy-safe output.

**Top validated fastest 50s**

- Lachlan Wu: 18 balls, 54*, Summer 2021/22, `51c4815c-654f-4bd5-8b31-ad7acd0a5c3c`
- Sidhi Budhiraja: 18 balls, 50*, Summer 2025/26, `ea96137b-af31-49bf-adf7-6686901853b2`
- Jacques Wildon: 20 balls, 72, Summer 2025/26, `7d59dc80-2d12-4a33-8ad9-7a28ae294240`
- Billy Skepper: 21 balls, 55, Summer 2025/26, `6ed4a325-c3c7-422b-8ee0-77c5ef92a8e3`
- Emma Gasper: 21 balls, 50*, Summer 2025/26, `594abb07-ac3f-4066-be4f-3842e24db51e`

**Top validated fastest 100s**

- Sebastian Fernandez: 71 balls, 100, Summer 2023/24, `5305074c-d34a-4b4c-b412-e1a3d2746639`
- Jake Drummond: 73 balls, 100*, Summer 2025/26, `079d7663-89d0-4fcb-bb04-f157cbda59d4`
- Shahroze Haris: 79 balls, 129, Summer 2024/25, `6dda2108-b21b-44b0-afaf-422e20960ee8`
- Loris Bayly: 79 balls, 100*, Summer 2024/25, `43cab805-842a-4c02-92cc-b573eab87f55`
- Anurag Gade: 82 balls, 103*, Summer 2023/24, `337f30e3-c277-4489-a1ae-488e4cb3c148`

### Plenty

- Deploy-safe rows: 745 before, 704 after.
- Post-fix rows under hard threshold: 0.
- Validation exclusions in local milestone builder: 153.
- Invalid source cumulative run warnings: 35.
- Result: no impossible fastest 50/100 rows remain in deploy-safe output.

**Top validated fastest 50s**

- Ashley Coles: 24 balls, 66*, Summer 2021/22, `c1259b74-50a4-494b-9a91-3138bcd745bd`
- Pino Tino: 26 balls, 50*, Summer 2024/25, `68ae8d24-c9f8-407f-b22f-1ca7f2706ea4`
- Ethan Weir: 27 balls, 79*, Summer 2020/21, `f0deaefc-8bcb-4631-82ae-c67d72937782`
- Cillian Wenholz: 27 balls, 70*, Summer 2025/26, `10a3f2d4-f0a2-4440-b2a5-8f6dddc6da1b`
- Liam Banthorpe: 28 balls, 78, Summer 2021/22, `6cabdec9-5928-4395-9662-df27fa26fdc4`

**Top validated fastest 100s**

- Cillian Wenholz: 55 balls, 109*, Summer 2025/26, `0ba0755c-1b75-4425-b04a-8e09223594fd`
- Chalitha Chamoda: 77 balls, 112, Summer 2023/24, `61805051-a6e2-4951-b403-268b8bba5a0a`
- Nick Strangwick: 81 balls, 118, Summer 2023/24, `11b80ddf-d912-46b1-bdf2-3908b2e82f5f`
- Tanuj Rajarathna: 82 balls, 104*, Summer 2021/22, `c707ab0b-7637-4bdc-8950-e9c0af3d26b0`
- Tanuj Namalge: 83 balls, 104*, Summer 2023/24, `d385d2b8-e124-4f72-97d5-169f6c8a19de`

### Reynella

- Deploy-safe rows: 702 before, 645 after.
- Post-fix rows under hard threshold: 0.
- Validation exclusions in local milestone builder: 257.
- Invalid source cumulative run warnings: 14.
- Result: no impossible fastest 50/100 rows remain in deploy-safe output.

**Top validated fastest 50s**

- Jonathon Hague: 24 balls, 60, Summer 2023/24, `126ec988-34ef-42e8-ba85-7973c1539722`
- Matthew Russell: 28 balls, 60, Summer 2024/25, `8cfd6490-1b43-42e8-8c0f-990836ed5df7`
- Matthew Russell: 29 balls, 61, Summer 2020/21, `81151582-5e05-4df0-898a-70dd36a2d31d`
- Daniel Rabbett: 32 balls, 69*, Summer 2024/25, `74063348-3725-4685-90c8-ab84ce15058f`
- Jack Briggs: 32 balls, 54*, Summer 2024/25, `a3fea0c0-bcef-4a79-8999-d002ae931065`

**Top validated fastest 100s**

- Joshua Leister-Mitchell: 72 balls, 100*, Summer 2025/26, `96e6a493-50e5-455e-8f6d-abc08b6f0503`
- Jayden Simons: 77 balls, 102*, Summer 2025/26, `79c8590b-32d8-4c34-949d-7ec70d7dfa16`
- Richard Gabb: 78 balls, 118, Summer 2021/22, `2d939e0a-f495-4ffa-9c67-c4de05109230`
- Jayden Simons: 84 balls, 101*, Summer 2025/26, `4ef953ac-95a3-4776-99d6-deec0b91ea89`
- Josh Burrows: 94 balls, 118, Summer 2021/22, `083b4df2-a0fa-4c15-ac9e-5bbb292aa6ea`

### Georges River District

- Deploy-safe rows: 555 before, 514 after.
- Post-fix rows under hard threshold: 0.
- Validation exclusions in local milestone builder: 105.
- Invalid source cumulative run warnings: 12.
- Result: no impossible fastest 50/100 rows remain in deploy-safe output.

**Top validated fastest 50s**

- Balasubramaniyan Krishnamoorthy: 23 balls, 104*, Summer 2024/25, `09c17e57-c276-4997-9e23-bbed226211cc`
- Luke Hawksworth: 28 balls, 65, Summer 2024/25, `007e7356-a906-4c2b-ae03-fca90d1b63c2`
- Ryan Croom: 29 balls, 91, Summer 2024/25, `55ad78e4-fabc-4074-8fa8-d0412012199d`
- Balasubramaniyan Krishnamoorthy: 29 balls, 53*, Summer 2024/25, `c9d0c352-9c4f-4489-90fc-e53b27883ec2`
- Ryan Croom: 32 balls, 63*, Summer 2019/20, `dc475e18-8856-4be1-812e-f6e321263693`

**Top validated fastest 100s**

- Balasubramaniyan Krishnamoorthy: 58 balls, 104*, Summer 2024/25, `09c17e57-c276-4997-9e23-bbed226211cc`
- Syed Haider Bukhari: 82 balls, 191*, Summer 2024/25, `e15a6d92-9f27-41e3-9eae-b180e4d8a388`
- Benjamin Vella: 87 balls, 114, Summer 2016/17, `757269f1-46f9-482c-aafb-c761ac0e16df`
- James Kirkness: 94 balls, 146, Summer 2014/15, `1da5e521-4f7a-4165-bc97-322e601b1b3a`
- Christopher McArthur: 97 balls, 116*, Summer 2023/24, `068e49f0-32cb-47e0-983c-691e52449f7e`

### FVCC

- Deploy-safe rows: 199 before, 187 after.
- Post-fix rows under hard threshold: 0.
- Validation exclusions in local milestone builder: 37.
- Invalid source cumulative run warnings: 2.
- Result: no impossible fastest 50/100 rows remain in deploy-safe output.

**Top validated fastest 50s**

- Kalpeshkumar Patel: 19 balls, 52, Summer 2024/25, `386f5e7d-0c8b-408c-83ac-443ce1c272b0`
- Armaan Datta: 25 balls, 102*, , `57c3ff16-7f4b-46e1-a8fa-a255ff6d7ebb`
- Armaan Datta: 25 balls, 52*, , `ea5b3501-a238-4319-a130-26a2ede25abc`
- Predheesh Valayil Sivanandan: 25 balls, 51, Summer 2024/25, `e7d82264-d76f-41f6-b938-165cd8e1ffa3`
- Kalpeshkumar Patel: 29 balls, 64, Summer 2022/23, `9ba6e3a3-5ff7-466e-9535-2950c6f4054d`

**Top validated fastest 100s**

- Armaan Datta: 49 balls, 102*, , `57c3ff16-7f4b-46e1-a8fa-a255ff6d7ebb`
- Baurel D'Mello: 66 balls, 130, Summer 2024/25, `386f5e7d-0c8b-408c-83ac-443ce1c272b0`
