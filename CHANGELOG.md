# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

## [4.0.0](https://github.com/tks18/personal-finance-etl/compare/3.6.0...4.0.0) (2026-08-10)


### Bug Fixes 🛠

* **engines/analytics:** implement more details in log ([0909af3](https://github.com/tks18/personal-finance-etl/commit/0909af36248c10d96135c1bd33398157be1e6d31))
* **engines/benchmark:** fix edge cases, add logging with more details ([9e134c7](https://github.com/tks18/personal-finance-etl/commit/9e134c7ee40b527caad61ed81fae62a4eb081ae5))
* **engines/presentattions:** remove * 100 in monte carlo result for consistency with other outputs ([76149d1](https://github.com/tks18/personal-finance-etl/commit/76149d1fc4a9299626f8355d8e32725963c987f3))
* **extract:** excel_extractor: more proper error handling ([0a9831f](https://github.com/tks18/personal-finance-etl/commit/0a9831ff7bd4f5641e290cd4bc0b479061a3eed8))


### Code Refactoring 🖌

* **utils:** misc refactor ([cfce092](https://github.com/tks18/personal-finance-etl/commit/cfce09239c3f679374b3992032dc37b735230527))


### Features 🔥

* **config/finance_rules:** update convert_to_db func to handle any new parameters automatically ([644a7b6](https://github.com/tks18/personal-finance-etl/commit/644a7b6f0d42cca44b821f6957a6498c24e4523d))
* **config/settings:** add function to convert to db records for meta ingestion ([1cda32b](https://github.com/tks18/personal-finance-etl/commit/1cda32bf8756d2f0aca2b79420c99db44802aaeb))
* **engine/benchmark:** remove the cache manager and implement it natively in the persistent db ([e16a9ff](https://github.com/tks18/personal-finance-etl/commit/e16a9ff5826a192be107cfaf759d56c6cf82bcb8))
* **extract:** add data source meta to the csv sources ([65304b2](https://github.com/tks18/personal-finance-etl/commit/65304b2db732dc9b00f4659b2c545a0e746dd4be))
* **load/schema:** add schemas / replace schemas to match medallion architecture ([6dce5c0](https://github.com/tks18/personal-finance-etl/commit/6dce5c036a6ac2e4387ec5a3f76fc7893dd36e44))
* **load:** add metadata db manager ([c885819](https://github.com/tks18/personal-finance-etl/commit/c8858194284ad686760a7015883b50f47f3dee80))
* **load:** file_tracker: this will help in hashing, tracking of incremental files ([d322102](https://github.com/tks18/personal-finance-etl/commit/d3221027fb92105a095a909f1c2d7635760508df))
* **load:** implement bronze db manager ([67ba00f](https://github.com/tks18/personal-finance-etl/commit/67ba00f4733d099112261da73528756be9612089))
* **load:** implement gold db manager ([d6ab286](https://github.com/tks18/personal-finance-etl/commit/d6ab28662591f0fd6104ec318d5a379cbaf5c9dc))
* **load:** implement silver db manager ([d0bed8f](https://github.com/tks18/personal-finance-etl/commit/d0bed8f7911a97869d233efe8f6b6eb5b6a3d132))
* **load:** reframe database manager to central duck db manager ([60fca04](https://github.com/tks18/personal-finance-etl/commit/60fca041a9aaf98e9ceb82a439e24b459b171bbd))
* **pipeline/core:** support for incremental extractor for medallion arch ([6a757d5](https://github.com/tks18/personal-finance-etl/commit/6a757d5afed73d59d1e725ee185d30691d475d3e))
* **pipeline:** orchestrate the medallion pipeline with proper run tracking ([55720da](https://github.com/tks18/personal-finance-etl/commit/55720da61c92168224cbf37256f6a870ba604af5))
* **ui:** add a btn to snapshot DB at point in time ([833ebb2](https://github.com/tks18/personal-finance-etl/commit/833ebb2d3b21412d4b1ae558ee3fe239765932fc))


### Docs 📃

* add tech guides for new data sources, new presentation tables ([3e0da18](https://github.com/tks18/personal-finance-etl/commit/3e0da18c46e5696a54164ccc9c8e023d60ce8562))
* **readme:** update readme to reflect recent changes ([efabaff](https://github.com/tks18/personal-finance-etl/commit/efabaff6d9dc16185c6a9b0f8e08ccc99b528b87))

## [3.6.0](https://github.com/tks18/personal-finance-etl/compare/3.5.1...3.6.0) (2026-08-07)


### Features 🔥

* **engines/presentations:** upgrade monte carlo to account for market shifts, de-risking & more ([5258f3d](https://github.com/tks18/personal-finance-etl/commit/5258f3d4e4737e5b5b9ba2b5cd3652df9693c56b))
* **load/schema:** integrate the new columns ([c248679](https://github.com/tks18/personal-finance-etl/commit/c24867988e74aec13d0e0f07456098982dbe9599))


### Code Refactoring 🖌

* update docs, add configs ([c035d63](https://github.com/tks18/personal-finance-etl/commit/c035d63b68519243998e070c2dd6c04565193370))


### Docs 📃

* update readme ([69fdcce](https://github.com/tks18/personal-finance-etl/commit/69fdcce6e0ea13316d351bea4939d8c1af8fe501))


### Styling 🎨

* linter fixes ([fcdec86](https://github.com/tks18/personal-finance-etl/commit/fcdec861ae7a8733889bc0a2344f52ee11684c95))

### [3.5.1](https://github.com/tks18/personal-finance-etl/compare/3.5.0...3.5.1) (2026-08-07)


### Code Refactoring 🖌

* **engines/presentations:** proper refactor into maintainable modules ([d59b0e4](https://github.com/tks18/personal-finance-etl/commit/d59b0e4073b377c2f52f000086b42e6fb73d078e))


### Build System 🏗

* add types for psutils ([6842eab](https://github.com/tks18/personal-finance-etl/commit/6842eab0819e3371ea36caeb50815145c5a764ee))


### Docs 📃

* update guides, readme ([dab7a75](https://github.com/tks18/personal-finance-etl/commit/dab7a75c3229b70266ee16edb5791d0e7ee867d5))

## [3.5.0](https://github.com/tks18/personal-finance-etl/compare/3.4.1...3.5.0) (2026-08-07)


### Bug Fixes 🛠

* remove incremental refresh mode ([42706dd](https://github.com/tks18/personal-finance-etl/commit/42706dd0fc30ec7a198bac5df2d3daf6c6ee412c))


### Features 🔥

* consolidate presentation tables to domain specific areas instead of 15 tables ([e06f3e1](https://github.com/tks18/personal-finance-etl/commit/e06f3e16d576a4be25b9aff59caa994d7668d47b))


### Styling 🎨

* lint fixes ([6ca2597](https://github.com/tks18/personal-finance-etl/commit/6ca2597a3b3f294452c86fe00774808c87814b36))
* lint fixes ([22ab630](https://github.com/tks18/personal-finance-etl/commit/22ab6304dbc95e92a527fcfb04292990d5b942f0))

### [3.4.1](https://github.com/tks18/personal-finance-etl/compare/3.4.0...3.4.1) (2026-08-06)


### Reverts ◀

* revert back to 3.4.0 ([590fe05](https://github.com/tks18/personal-finance-etl/commit/590fe05c7dd32c962392d87b9f9e6e84a83d5988))
* revert to fd69f74 ([72fac0e](https://github.com/tks18/personal-finance-etl/commit/72fac0ead7e91f2ecb1944edf4d60231e8cb024c))


### Bug Fixes 🛠

* fix redudant columns ([ec0d77f](https://github.com/tks18/personal-finance-etl/commit/ec0d77fe362fe8a6d920aa76bf5736da607898b4))

## [3.4.0](https://github.com/tks18/personal-finance-etl/compare/3.3.0...3.4.0) (2026-08-06)


### Build System 🏗

* **pyproject:** add numba for jit ([de5f8fb](https://github.com/tks18/personal-finance-etl/commit/de5f8fb94ecd4d59615a99c3931dc5d9bdefcc5e))


### Docs 📃

* add FIRE Guide ([2523806](https://github.com/tks18/personal-finance-etl/commit/25238069d16d1cab6ff6d04b8f871e4917919b2c))
* **roadmap:** add roadmap ([3475271](https://github.com/tks18/personal-finance-etl/commit/34752716498c42eb435c832425b520a50f469090))


### Code Refactoring 🖌

* add ddls, update sample config, some minor fixes ([fd69f74](https://github.com/tks18/personal-finance-etl/commit/fd69f7429bbfe4410162421a3e21a8ae4f61ff13))
* **settings:** bring out more rules outside to fin_rules config ([a190a22](https://github.com/tks18/personal-finance-etl/commit/a190a2245bfdc801bf8aaf9b2347998a693c70a5))


### Features 🔥

* **cache:** implement a central cache manager for raw files ([f3ae9e6](https://github.com/tks18/personal-finance-etl/commit/f3ae9e60d518d3dfb9f7ed929d1c5f8a9490b723))
* **config:** new parameters for budgeting and forecasting ([1951ecb](https://github.com/tks18/personal-finance-etl/commit/1951ecb02e94e8ba78b71c3b891e8805c384e527))
* **engines/presentations:** budgeting and forecasting module ([b73c504](https://github.com/tks18/personal-finance-etl/commit/b73c504c9ab1416eef106748e1442b71835190a5))
* **engines/presentations:** investment snapshot presentation module ([f0488ea](https://github.com/tks18/personal-finance-etl/commit/f0488ea1582f22bca1e0c60fd2fde4cb2abe2bbf))
* **engines/presentations:** monthly cashflow summary presentation module ([9a1ee0c](https://github.com/tks18/personal-finance-etl/commit/9a1ee0cfd8138b358ac0a2f4cf264e4c91e76308))
* implement a incremental load strategy ([c8da49c](https://github.com/tks18/personal-finance-etl/commit/c8da49c8eb09b6f251ea97517bc46723e3dc858b))


### Tests 🧪

* sampe config file ([5a2e7ef](https://github.com/tks18/personal-finance-etl/commit/5a2e7ef4165520c3727bcb4bef4f8d772f0578df))

## [3.3.0](https://github.com/tks18/personal-finance-etl/compare/3.2.0...3.3.0) (2026-08-04)


### Features 🔥

* **engines/analytics:** add some helper total columns ([c6db299](https://github.com/tks18/personal-finance-etl/commit/c6db2998d3e5376baee6a8f0b299e7b2746b34a6))

## [3.2.0](https://github.com/tks18/personal-finance-etl/compare/3.1.2...3.2.0) (2026-08-04)


### Features 🔥

* **engines/analytics:** split loss into LTCL and STCL for tax purposes ([b3e86fd](https://github.com/tks18/personal-finance-etl/commit/b3e86fd913f1b4b7a2db24dd950155e2d4549fac))


### Bug Fixes 🛠

* **engines/analytics:** fix loss being coming up as portfolio total instead of Lot Total ([6028b88](https://github.com/tks18/personal-finance-etl/commit/6028b88f71f791a2fc6af74aa35f9f4720dca584))
* **engines/analytics:** fix realized events ([b83f0d2](https://github.com/tks18/personal-finance-etl/commit/b83f0d2b9786b22866061830b111f714f1436e99))
* **engines/analytics:** fix realized events not being properly captured for gain/loss calc ([d31b4bb](https://github.com/tks18/personal-finance-etl/commit/d31b4bb9c5c4f9bb4f6f6a7f4c64f9c89a09e067))


### Docs 📃

* minor update to docs ([62d205d](https://github.com/tks18/personal-finance-etl/commit/62d205d20eb883c3570bbd18ab16a66294ee8589))

### [3.1.2](https://github.com/tks18/personal-finance-etl/compare/3.1.1...3.1.2) (2026-08-04)


### Docs 📃

* update metrics guide ([c9ba2da](https://github.com/tks18/personal-finance-etl/commit/c9ba2dadef9b5deea00838f420e7f4bec7d0b764))

### [3.1.1](https://github.com/tks18/personal-finance-etl/compare/3.1.0...3.1.1) (2026-08-04)


### Docs 📃

* add presentation and analytics layer guide ([d81f719](https://github.com/tks18/personal-finance-etl/commit/d81f719d5d1bd46e6fcb7ad98c27cc170806891f))
* **readme:** dialed down genz vibes ([277c39d](https://github.com/tks18/personal-finance-etl/commit/277c39dbe60f2d1af87326727d3d2984a6715acf))
* update descriptions ([05cb589](https://github.com/tks18/personal-finance-etl/commit/05cb589fc56039b23cdd48b345b5fa6c0eff64c1))

## [3.1.0](https://github.com/tks18/personal-finance-etl/compare/3.0.0...3.1.0) (2026-08-04)


### Bug Fixes 🛠

* **engines/presentation:** fix monte-carlo to have variable withdrawal rate ([d45c7f2](https://github.com/tks18/personal-finance-etl/commit/d45c7f21c084dc139071f14b0f191241d7e1a9ab))

## [3.0.0](https://github.com/tks18/personal-finance-etl/compare/2.4.0...3.0.0) (2026-08-04)


### Styling 🎨

* linter fixes ([68c8418](https://github.com/tks18/personal-finance-etl/commit/68c84181b0c5e03178ddb0eadda7623a62b246b7))


### Features 🔥

* **engines/analytics:** enhance the speed for processing an isin ([6f3b43c](https://github.com/tks18/personal-finance-etl/commit/6f3b43ce228f44bed8afb2777b3c5640fdd6ee29))
* **engines/presentations:** introduce math fixes and enhancements and refactor to sep mods ([f67bcfb](https://github.com/tks18/personal-finance-etl/commit/f67bcfb5834bb922a7d6ab7ee7c46e4de42166c7))
* **load:** add ddl for new columns and tables ([5128905](https://github.com/tks18/personal-finance-etl/commit/5128905bce5cbbd64aa33357637660beacb72a4f))
* **logging:** add debug level logging at various places ([3457ede](https://github.com/tks18/personal-finance-etl/commit/3457ede17555dc23d142c53011b5298fbaa5e243))
* **utils:** logger - add a file level debug logger for detailed logging ([ac84c58](https://github.com/tks18/personal-finance-etl/commit/ac84c58aca6e07bbe71f0dbfa01b1674be5c3cb7))


### Docs 📃

* update readme and metrics guide to add new metrics ([77adaa1](https://github.com/tks18/personal-finance-etl/commit/77adaa1479142835e48a30397aaed37d3a10f44d))

## [2.4.0](https://github.com/tks18/personal-finance-etl/compare/2.3.0...2.4.0) (2026-08-03)


### Bug Fixes 🛠

* **logging:** overhaul logging to properly add correct metrics ([c494024](https://github.com/tks18/personal-finance-etl/commit/c4940246111c97dd6af6cf50af7d833f2c3f4870))


### Code Refactoring 🖌

* **helpers:** refactor tax to macro table ([a781444](https://github.com/tks18/personal-finance-etl/commit/a78144413fbc1873ee030906c3a77dca2e6b6116))
* **pipeline:** refactor tax to macro ([534d049](https://github.com/tks18/personal-finance-etl/commit/534d0491d170cada5ee9e9fa85ae79cc7098a485))
* rename tax parameters to macro parameters ([a2d888a](https://github.com/tks18/personal-finance-etl/commit/a2d888adae746c0419ce0f7c8bbffd6f94276f8d))
* rename tax table to macro table ([9a4f4c9](https://github.com/tks18/personal-finance-etl/commit/9a4f4c951180c556f7e782d11479ef47b2c13b38))
* rename tax to macro, change invt analytics to quant engine ([72ef069](https://github.com/tks18/personal-finance-etl/commit/72ef069c5b329053a36982f82f314990efd3046a))


### Styling 🎨

* change the content to correct reflect the state ([4f580ae](https://github.com/tks18/personal-finance-etl/commit/4f580ae6c48f7b2e4d56cb46b131ba546f4be071))


### Features 🔥

* **config:** introduce new parameters to configure the app ([498fdbb](https://github.com/tks18/personal-finance-etl/commit/498fdbb59da6a692c0c7a9d603a8b1c5c6151e01))
* **engine/presentations:** harden maths, quant, metrics, introduce correct metrics ([7b5ba6f](https://github.com/tks18/personal-finance-etl/commit/7b5ba6f4851efe78918a1d75142d1ac817c0c322))
* **load/schema:** update duckdb ddl ([d3feb0e](https://github.com/tks18/personal-finance-etl/commit/d3feb0e74efac9d94946994afb4245ce3f76e214))
* **transform:** add all the rules to the dim tables ([440b685](https://github.com/tks18/personal-finance-etl/commit/440b6854b7f8fb9cc7c6d9bb2abd9a429d4656ad))


### Docs 📃

* add a metrics guide for understanding ([a99762b](https://github.com/tks18/personal-finance-etl/commit/a99762b272c6a1515d1be9c5f592c9ee2b07f5dc))
* update readme to reflect recent changes ([ef39804](https://github.com/tks18/personal-finance-etl/commit/ef39804487e08e03c028f9655890241688214623))

## [2.3.0](https://github.com/tks18/personal-finance-etl/compare/2.2.0...2.3.0) (2026-08-02)


### Build System 🏗

* add pydantic ([ddebe1e](https://github.com/tks18/personal-finance-etl/commit/ddebe1eb939656c3562b66198ed9eb5b438cac6b))


### Code Refactoring 🖌

* **config:** move to pydantic ([d76b8f8](https://github.com/tks18/personal-finance-etl/commit/d76b8f8a0254e8e77cb20cb2a78147f6ab5761fa))
* **load:** rules refactor + reorder the cols ([804b16d](https://github.com/tks18/personal-finance-etl/commit/804b16d03b468d11548e1e0d359fd644a818b4e4))


### Features 🔥

* **config:** introduce new config to handle financial rules / assumptions ([ef1dffa](https://github.com/tks18/personal-finance-etl/commit/ef1dffa7cab2d3f4459416f9b896aff077964208))
* **engines/analytics:** add rules to context + some fixes for calcs ([a64dd7d](https://github.com/tks18/personal-finance-etl/commit/a64dd7df3db206fb02936c67e3e9efba503dab87))
* **engines/presentations:** integrate rules and add various metrics based on that ([b0f9e18](https://github.com/tks18/personal-finance-etl/commit/b0f9e1807ccfcd258f7b4968c64b5c8e28696388))
* **load/schema:** add rules metadata to the db ([ca480a6](https://github.com/tks18/personal-finance-etl/commit/ca480a6aa6f87d8faaa7fa1df549555156043f7a))
* **pipeline:** integrate rules ([8e7e526](https://github.com/tks18/personal-finance-etl/commit/8e7e526bb616ee8ff9bcfa7bcd8f4819de12aa0f))
* **pipeline:** integrate rules in the pipeline ([ce4e2e7](https://github.com/tks18/personal-finance-etl/commit/ce4e2e7d56fa6fb74075a2d70b48a522f9569667))
* **transform:** add metrics using financial rules ([2d5cea3](https://github.com/tks18/personal-finance-etl/commit/2d5cea31139df09f70c909a3cb87c163cd3e283b))
* **ui:** integrate ui funcs for financial rules ([aa1e951](https://github.com/tks18/personal-finance-etl/commit/aa1e9517ae8e849687b211b88eee0a3c9b513f49))


### Tests 🧪

* add sample financial rules config ([0bbfc4c](https://github.com/tks18/personal-finance-etl/commit/0bbfc4cc1edfe70535e3612796042f23b1e501dc))

## [2.2.0](https://github.com/tks18/personal-finance-etl/compare/2.1.0...2.2.0) (2026-08-01)


### CI 🛠

* **package.json:** add uv scripts to package.json ([3cc6450](https://github.com/tks18/personal-finance-etl/commit/3cc6450b715bfde3a18dcf6f36d9b99746b5db0e))


### Bug Fixes 🛠

* **engines/analytics:** fix cagr calculation ([b5c4d9c](https://github.com/tks18/personal-finance-etl/commit/b5c4d9c09f7db5630b9623e6c2a8c438d2c1dbd1))
* **engines/analytics:** xirr array fix ([2edeefd](https://github.com/tks18/personal-finance-etl/commit/2edeefdac123c832d3ace2d4d33636cf67372a8e))


### Code Refactoring 🖌

* **engines/analytics:** minor refactor to dedupe code ([ec79773](https://github.com/tks18/personal-finance-etl/commit/ec79773f0d95a534cd64401f9b44fde6d69ca443))
* **engines/analytics:** now uses risk free rate from tax table ([c383e8e](https://github.com/tks18/personal-finance-etl/commit/c383e8e5eb0853199fcd0d1b33ba8a5bc5b00ac8))
* minor refactor ([ab8fae8](https://github.com/tks18/personal-finance-etl/commit/ab8fae8ab28f482ea74cb97b5e211c3287bf2656))
* minor refactor ([a4aca38](https://github.com/tks18/personal-finance-etl/commit/a4aca38017a60c91e16a792ee1eb84c7e4c8b425))
* minor refactors ([1fbada5](https://github.com/tks18/personal-finance-etl/commit/1fbada55bd058cf8aa9b07d042b71a85d649af2a))


### Features 🔥

* **engines/analytics:** add function to extract risk free rate ([7f45498](https://github.com/tks18/personal-finance-etl/commit/7f4549868ef353fbcf7d09b08b3838aeee8cd072))
* **engines/presentations:** include various metrics for personal finance management ([fd21dca](https://github.com/tks18/personal-finance-etl/commit/fd21dca30e8f12eca34b6efc1494f532c7b95f43))
* schema update to tax_rates table ([8888d33](https://github.com/tks18/personal-finance-etl/commit/8888d33609b3a5d7141703a315c9718bd5e47822))

## [2.1.0](https://github.com/tks18/personal-finance-etl/compare/2.0.0...2.1.0) (2026-08-01)


### Build System 🏗

* add psutil module ([8ab235c](https://github.com/tks18/personal-finance-etl/commit/8ab235cbbd170f9c59ffd2c2910dafa3ae4c61e1))


### Bug Fixes 🛠

* **utils:** logger - add proper logging formatting ([44ccb29](https://github.com/tks18/personal-finance-etl/commit/44ccb2916911a30855c462cd07203aa9d6aac600))


### Features 🔥

* **config:** remove hardcoded literals to configs ([180a6db](https://github.com/tks18/personal-finance-etl/commit/180a6db591c0628153ef3ce32c27a4f859be8093))
* **engines/analytics:** add a group processor for a future update to reuse code at diff grp lvls ([e3e6f92](https://github.com/tks18/personal-finance-etl/commit/e3e6f9224d8fe368f3505574019d5a56172dbc4f))
* **engines/analytics:** allow group processing ([081c4d4](https://github.com/tks18/personal-finance-etl/commit/081c4d4d37cd51ca07073089046ee7135a833607))
* **engines/analytics:** allow processing at different group levels ([41f1ced](https://github.com/tks18/personal-finance-etl/commit/41f1cedb2bee28ec146b1e9c8df63f94c6435077))
* **engines/analytics:** integrate group processor for processing at diff group levels ([36a00ea](https://github.com/tks18/personal-finance-etl/commit/36a00ea5306b1a55fd32ca61c33432f1b680c528))
* **engines/analytics:** orchestrate the entire invt analytics engine ([e8c063a](https://github.com/tks18/personal-finance-etl/commit/e8c063a42104e2ca9f4585eb962fa83a9dbd68d9))
* **engines/presentations:** add inflation related calculations + logging refactor ([53b4bfe](https://github.com/tks18/personal-finance-etl/commit/53b4bfe164f24badd3a5a4a106c8934ffabc9717))
* **extract:** add a new source: inflation rates ([10f13f2](https://github.com/tks18/personal-finance-etl/commit/10f13f24eb64620c578d20b6bcc34606126bb46b))
* **load/schema:** add ddl for inflation related cols across presentation tables ([4d97d5f](https://github.com/tks18/personal-finance-etl/commit/4d97d5f8b8e9ae05a72374347b64bcb6a2c4fceb))
* **load/schema:** enforce not null, also add invt group views, inflation related cols ([1096684](https://github.com/tks18/personal-finance-etl/commit/1096684d4df7d0ef2f838be8f3f98d1b4dacf8c5))
* **utils:** models - add a inflation raw data extraction result ([15ebc60](https://github.com/tks18/personal-finance-etl/commit/15ebc6089e71be2a43266e722ccb8f99c6c7a12a))


### Code Refactoring 🖌

* **engines/analytics:** logging refactor ([803bf2f](https://github.com/tks18/personal-finance-etl/commit/803bf2fbaeb7517633df2dc3978312ee905c37d5))
* **engines/benchmark:** logging + polars refactor (move form pandas) ([b48835f](https://github.com/tks18/personal-finance-etl/commit/b48835f2a34b674ff745eeb77641252a99be0f50))
* **extract:** logging refactor + sqlite optimization ([f1f8025](https://github.com/tks18/personal-finance-etl/commit/f1f8025b04e298a3f123b74c8ac3114f78505622))
* **load:** logging refac + duckdb optimzations and code dedupe ([2cbbf14](https://github.com/tks18/personal-finance-etl/commit/2cbbf140b93a2da4704635a4975a86861ed5926a))
* **pipeline:** logging refac + inflation tables + orchestration optimizations ([88a6042](https://github.com/tks18/personal-finance-etl/commit/88a6042117307b76906a1abc17bdbe2d667b32ad))
* **transform:** polars query optimization ([71b1a82](https://github.com/tks18/personal-finance-etl/commit/71b1a82ff0b4719c9fffd744d91eb768c431a29d))

## [2.0.0](https://github.com/tks18/personal-finance-etl/compare/1.8.5...2.0.0) (2026-07-31)


### Docs 📃

* **transform:** fix docstring/comments ([0a79e5d](https://github.com/tks18/personal-finance-etl/commit/0a79e5dce699e4d8055ebc885e48c68acecd71fe))


### Bug Fixes 🛠

* **engines/analytics:** tax - more maintainable rule using tuple and dict mappings ([f2e618e](https://github.com/tks18/personal-finance-etl/commit/f2e618eedf3bad02e065658e2c55d4f07fa7cf29))
* **engines/presentations:** some common polars query optimizations ([6266452](https://github.com/tks18/personal-finance-etl/commit/62664526bde17f31e6f12cae00616593992604e2))
* **extract:** add logging if no files found ([64f31c8](https://github.com/tks18/personal-finance-etl/commit/64f31c87526a070c295263c0577203d874489e26))
* **extract:** sqlite - add extension in the glob search ([56bcce7](https://github.com/tks18/personal-finance-etl/commit/56bcce7afff7720e1a4d9d149a7310f977d82b95))
* **helpers:** add common polars date parsng function ([459b644](https://github.com/tks18/personal-finance-etl/commit/459b644290f3ed8cc377f8e77f97133db69111a1))
* **load/schema:** fix schema namings ([aa93cde](https://github.com/tks18/personal-finance-etl/commit/aa93cde3fa8e350599f1bbe7ecad88c81c2b8509))
* **load:** database: add cleanups on fail ([a330aed](https://github.com/tks18/personal-finance-etl/commit/a330aed45369badc11b3a79d97a3bfa8c99ed2c7))
* **pipeline/core:** add validation before collect all ([972e5b2](https://github.com/tks18/personal-finance-etl/commit/972e5b2e078d9349e1b1f6f5bb8c19415cf2602e))
* **pipeline:** add cleanup on pipeline fail ([5595ff8](https://github.com/tks18/personal-finance-etl/commit/5595ff8359f475ef5bdb3a5341b1400ce3e323f9))
* **transform:** add common pl query optimizations & fixes, dedupe code ([6173724](https://github.com/tks18/personal-finance-etl/commit/61737247f9c3373adc4361a45d7632d599774d1f))


### Build System 🏗

* add duckdb to move out of sqlite3 ([4da3fdf](https://github.com/tks18/personal-finance-etl/commit/4da3fdf6066daa24c4c6bde65ebe1050d2f012f5))


### Features 🔥

* **config:** settings - add validation and raise errors ([137b944](https://github.com/tks18/personal-finance-etl/commit/137b94405b95e3a5e4002d3ef6c4627f0d178ea0))
* **engines/analytics:** isin_pipeline - parallelerize the isin pipeline using futures ([294ddbc](https://github.com/tks18/personal-finance-etl/commit/294ddbc8a6b99513eb86479329ae02ced7cc6157))
* **engines/benchmark:** introduce new benchmark cache manager ([5b5c8f2](https://github.com/tks18/personal-finance-etl/commit/5b5c8f271d0708076138a3e5f500251551a73f54))
* **engines/presentations:** add a new advanced analytics views for more in depth insights ([9673031](https://github.com/tks18/personal-finance-etl/commit/9673031334b86125ec91d5f79df43c9f9ec21dac))
* **engines/presentations:** add a new monte carlo simulation for FIRE Forecasting ([4411179](https://github.com/tks18/personal-finance-etl/commit/44111797dd6fc02a5217b579a87c15d57d4132ac))
* **engines/presentations:** integrate advanced analytics engine ([7e114a7](https://github.com/tks18/personal-finance-etl/commit/7e114a7a8a485b9b11d87d6839e4607816f111d6))
* **load/db:** move to duckdb froms sqlite ([56a8c14](https://github.com/tks18/personal-finance-etl/commit/56a8c14616014f81c99195cfa53265b13296b4da))
* **load/schema:** add new presentation tables based on duckdb ddl ([667a42c](https://github.com/tks18/personal-finance-etl/commit/667a42c65ba23faaf70b517491bd0c6e7bfa1c80))
* **load/schema:** rewrite all sqlite3 ddl to duckdb ddl ([1d99f4d](https://github.com/tks18/personal-finance-etl/commit/1d99f4dfed0891f3946935d3c7cb0c097669f0b1))
* **pipeline:** now mf scheme mappings are configurable ([56c79ef](https://github.com/tks18/personal-finance-etl/commit/56c79ef4cd2e21c48b596805e7fb341a37167446))


### Code Refactoring 🖌

* **engine/benchmark:** refactor for better maintainability ([c15227c](https://github.com/tks18/personal-finance-etl/commit/c15227c5c2ceb6ba04f43b783c3c1fbe66b57a43))
* **extract:** excel - refactor common function and dedupe the code ([b1d4f47](https://github.com/tks18/personal-finance-etl/commit/b1d4f47fe82e8b2596d24ba0758c5656c00297e2))
* **pipeline/core:** minor refactors ([54b00c1](https://github.com/tks18/personal-finance-etl/commit/54b00c19a0a41b15209ccee14633f168a201d06e))
* **pipeline:** refactor to new db and other module refactors ([e7563c7](https://github.com/tks18/personal-finance-etl/commit/e7563c73e9e64d3617e218c2fed5bbe841fdd508))


### Tests 🧪

* correct the headless test file properly to use new modules ([1559b76](https://github.com/tks18/personal-finance-etl/commit/1559b76e5063a226e28e3c784b03633536feae21))

### [1.8.5](https://github.com/tks18/personal-finance-etl/compare/1.8.4...1.8.5) (2026-07-25)


### Bug Fixes 🛠

* **transform:** fix data type issue for amount column ([73bb402](https://github.com/tks18/personal-finance-etl/commit/73bb402c6c403b6a9f8fdd2931cceb61cd11ffca))

### [1.8.4](https://github.com/tks18/personal-finance-etl/compare/1.8.3...1.8.4) (2026-07-25)


### Bug Fixes 🛠

* **transform:** fix amount column ([e23aef5](https://github.com/tks18/personal-finance-etl/commit/e23aef5bf12fe0d277391b7d50755a9ea01e231e))

### [1.8.3](https://github.com/tks18/personal-finance-etl/compare/1.8.2...1.8.3) (2026-07-24)


### Bug Fixes 🛠

* **transform:** facts: fix amount column ([0354b68](https://github.com/tks18/personal-finance-etl/commit/0354b68bdb528462432b02e51136d2f319f92058))

### [1.8.2](https://github.com/tks18/personal-finance-etl/compare/1.8.1...1.8.2) (2026-07-23)


### Bug Fixes 🛠

* **load:** fix database journal mode ([e7f532c](https://github.com/tks18/personal-finance-etl/commit/e7f532cb695638320c1abec8147abf2ea452e492))

### [1.8.1](https://github.com/tks18/personal-finance-etl/compare/1.8.0...1.8.1) (2026-07-23)


### Bug Fixes 🛠

* **load:** remove journal mode after datas are written ([70b77a7](https://github.com/tks18/personal-finance-etl/commit/70b77a7678a274e2c9b275d94833e3b507f4bc8f))

## [1.8.0](https://github.com/tks18/personal-finance-etl/compare/1.7.0...1.8.0) (2026-07-22)


### Features 🔥

* **engines/presentations:** add new tables for spend, income and fire analytics ([ea98b83](https://github.com/tks18/personal-finance-etl/commit/ea98b83a9be2fd1fb74bbeae00bd0fdc207c2a7e))
* **load:** add schema ddl ([25222dd](https://github.com/tks18/personal-finance-etl/commit/25222ddf56d5a8511830487d7debaec7b4134efd))

## [1.7.0](https://github.com/tks18/personal-finance-etl/compare/1.6.0...1.7.0) (2026-07-21)


### Bug Fixes 🛠

* **engines:** presentation - trim out all historical months with no data ([977dd88](https://github.com/tks18/personal-finance-etl/commit/977dd88d2971e4c2de759db67e0e95213fbe873c))

## [1.6.0](https://github.com/tks18/personal-finance-etl/compare/1.5.0...1.6.0) (2026-07-21)


### Features 🔥

* **engines:** add a presentation engine for calculating various metrics ([51d4d8a](https://github.com/tks18/personal-finance-etl/commit/51d4d8a2a4cff300836746e0c7085f0a00359e92))
* **etl/pipeline:** add presentation dag to the flow ([699a851](https://github.com/tks18/personal-finance-etl/commit/699a8512ccdb2c402683e4fdadc23cc814f81e97))
* **load:** add presentation tables to ddl ([87280b3](https://github.com/tks18/personal-finance-etl/commit/87280b38621391d6b6f7f5cc26e91431034964dc))


### Docs 📃

* **readme:** update readme to add more rizz ([0a2d870](https://github.com/tks18/personal-finance-etl/commit/0a2d8702506aa973001f6a6acbe096122de66182))

## [1.5.0](https://github.com/tks18/personal-finance-etl/compare/1.4.0...1.5.0) (2026-07-21)


### Styling 🎨

* ruff linting fixes ([09cddf7](https://github.com/tks18/personal-finance-etl/commit/09cddf77656efefb64ef56f8899344737da76113))

## [1.4.0](https://github.com/tks18/personal-finance-etl/compare/1.3.0...1.4.0) (2026-07-21)


### Build System 🏗

* add vulture for finding dead code ([b5122e1](https://github.com/tks18/personal-finance-etl/commit/b5122e10d503f4678449621c4d196de8d09666ec))


### Features 🔥

* **config:** move to class based config module ([2064f0b](https://github.com/tks18/personal-finance-etl/commit/2064f0bb67e0ff639e1f68ccd9f6add72301b554))


### Code Refactoring 🖌

* **engine:** make the benchmark engine to oop, better folder struct ([2b022f9](https://github.com/tks18/personal-finance-etl/commit/2b022f90c6b967badb7ad4b642d2a29a20ce3f43))
* **engines:** refactor tax to analytics engine, better folder struct, also move to oop ([e3b4c46](https://github.com/tks18/personal-finance-etl/commit/e3b4c4601dbb3af4539d85b7a43f3b4bcd248366))
* **extract:** move csv related loading to extract folder only from transforms ([283d7cb](https://github.com/tks18/personal-finance-etl/commit/283d7cb1cb927f36215f13eecdcbd57c4218caf1))
* **extract:** move excel related loading to extract folder only ([3ae07b4](https://github.com/tks18/personal-finance-etl/commit/3ae07b42ba5a7ed4966d5863b6fa4021f0e956c9))
* **extract:** sqlite extract - move to oop based module ([417fbcb](https://github.com/tks18/personal-finance-etl/commit/417fbcb9836e4c1ad1bc8e66a1ce9179b6a893ad))
* **load:** move the db to separate modules, also now move to oop ([3360c06](https://github.com/tks18/personal-finance-etl/commit/3360c06fbbe0264c27d7ab3b688743d802c9c3bb))
* **pipeline:** refactor the etl pipeline to sizeable sub modules ([4e3dfc1](https://github.com/tks18/personal-finance-etl/commit/4e3dfc16186ef2eb8da01658be3dae0b186959b9))
* **pipeline:** use the new extract and transform modules ([6d4c6e9](https://github.com/tks18/personal-finance-etl/commit/6d4c6e9d1cc88725d3166095a55a35cc6787aae3))
* **transform:** refactor transform functions into sizeable sub modules ([1fe09f0](https://github.com/tks18/personal-finance-etl/commit/1fe09f0359b5ffdc1f7e1cd26c3d6c008ef1460c))
* **ui:** use the new config class for handling configs ([fe2ecd7](https://github.com/tks18/personal-finance-etl/commit/fe2ecd79670135a6f0a855bd2ba8099e72fe3b93))
* **utils:** models - add more tables in the extraction result, separation of extract and t'ion ([867cf21](https://github.com/tks18/personal-finance-etl/commit/867cf218fbbbdf2ce60fbabc4e1f94a3ed938e67))

## [1.3.0](https://github.com/tks18/personal-finance-etl/compare/1.2.0...1.3.0) (2026-07-20)


### Bug Fixes 🛠

* data types fixes ([bba6b21](https://github.com/tks18/personal-finance-etl/commit/bba6b213436c911ccc3f21fc12deb798908e27b7))

## [1.2.0](https://github.com/tks18/personal-finance-etl/compare/1.1.0...1.2.0) (2026-07-20)


### Styling 🎨

* linter and typing fixes for the whole codebase ([3789f8f](https://github.com/tks18/personal-finance-etl/commit/3789f8fd7bfa3dd34348a69c19810b0feb48b814))

## [1.1.0](https://github.com/tks18/personal-finance-etl/compare/1.0.2...1.1.0) (2026-07-20)


### CI 🛠

* add pyright, mypy and ruff for strong typing and linting support ([bf9645e](https://github.com/tks18/personal-finance-etl/commit/bf9645e51bb013d1e965d128aa230246a46b6b22))


### Features 🔥

* **utils:** add logger and database protocol models ([80484b5](https://github.com/tks18/personal-finance-etl/commit/80484b5c78fe28e4f7fb5adbb5ef3308664f1de1))


### Code Refactoring 🖌

* completely refactor for better typings, code maintainability ([fde93e6](https://github.com/tks18/personal-finance-etl/commit/fde93e607bab0ba12892980fbaeb022be5f74a31))
* **config:** refactor settings to follow SRP ([bab566d](https://github.com/tks18/personal-finance-etl/commit/bab566df37fad4125e712db2fdd23f34b3fea001))
* **engines/core:** fifo: refactor for better maintenance ([974d087](https://github.com/tks18/personal-finance-etl/commit/974d08786256094e9d8b06ae6a3a62c72bd95140))
* **engines/pipeline:** refactor for better typings ([3249208](https://github.com/tks18/personal-finance-etl/commit/324920812ad7b6b9d36260f412dcb8df61412760))
* **engines/rules:** add typings ([f7bb870](https://github.com/tks18/personal-finance-etl/commit/f7bb8700eba73c46ab11559a4ac26f9562e5cd6c))
* **engines:** full typing support ([142c645](https://github.com/tks18/personal-finance-etl/commit/142c645001d7d4acbbe86ad0f7d95a77aa2d1917))
* **utils:** better typing support ([34054f7](https://github.com/tks18/personal-finance-etl/commit/34054f723b6e7931a518a138d118868ce17acc28))

### [1.0.2](https://github.com/tks18/personal-finance-etl/compare/1.0.1...1.0.2) (2026-07-19)


### Bug Fixes 🛠

* linter fixes ([da02cea](https://github.com/tks18/personal-finance-etl/commit/da02ceab9b919d2a9dbba0f21b5591da7c48bede))

### [1.0.1](https://github.com/tks18/personal-finance-etl/compare/1.0.0...1.0.1) (2026-07-19)


### Bug Fixes 🛠

* **engines/core:** fix fifo: small check for linter ([58f1ca7](https://github.com/tks18/personal-finance-etl/commit/58f1ca712ab2494821c84b506555571ea2cd8038))

## [1.0.0](https://github.com/tks18/personal-finance-etl/compare/0.1.5...1.0.0) (2026-07-19)


### Features 🔥

* **engines/pipeline:** main processor for investment manager ([af103b6](https://github.com/tks18/personal-finance-etl/commit/af103b62c383497efa66685f189315aaa7fd2dee))
* **engines/pipeline:** write the post processing script that will run after data load ([1042838](https://github.com/tks18/personal-finance-etl/commit/10428386f3a5b1bd8a0c01c67aaa062403381215))
* **engines:** write the benchmark engine for handling the market bechmark data through yfinance ([eb7f193](https://github.com/tks18/personal-finance-etl/commit/eb7f193920676f9317a61bd279b77f88f0e5fefe))
* **engines:** write the main investment engine ([8b8fcb2](https://github.com/tks18/personal-finance-etl/commit/8b8fcb2bc2f64b61f67600d8971251bd34341eb2))
* **load:** setup the main db load module for init, optimize and loading data ([173ad56](https://github.com/tks18/personal-finance-etl/commit/173ad56565f34553e8503a767cfce046e016b7ac))
* **main:** completely modularize the app, add new features and this simply runs the ui mainloop ([89dc915](https://github.com/tks18/personal-finance-etl/commit/89dc9158601c244afab49742cc166aba430b209c))
* **pipeline:** orchestrate the entire ETL pipeline End-to-End ([b50c162](https://github.com/tks18/personal-finance-etl/commit/b50c162659801780a3adfafa3589ea69fb2780a8))
* **transform:** write the core transforms across various datasets ([c350d05](https://github.com/tks18/personal-finance-etl/commit/c350d0569ceacf95209f18588d4b3f0da4ed437b))
* **transform:** write transforms related to mutual funds ([9c8a6fa](https://github.com/tks18/personal-finance-etl/commit/9c8a6fa1da78790431ef719bd86463a393eb69c1))
* **transform:** write transforms related to stocks ([61fe666](https://github.com/tks18/personal-finance-etl/commit/61fe66678939fd24f87e2773e6576413047e8f3a))
* **ui:** create custom-tkinter app ([5cb0ea9](https://github.com/tks18/personal-finance-etl/commit/5cb0ea9a4035fc39b4235b6ada61915a1923b637))
* **ui:** setup the base ui tab ([0839548](https://github.com/tks18/personal-finance-etl/commit/083954863c9071a16aebd12cbdf2af0546acbeef))


### Tests 🧪

* add some sample config and tests ([8587c1b](https://github.com/tks18/personal-finance-etl/commit/8587c1bb75003a89ee318862f2c02e40682d964a))


### Docs 📃

* **readme:** add a personalized readme ([da503b5](https://github.com/tks18/personal-finance-etl/commit/da503b58e8c8d77ee95341e3ec81dfde6278f926))

### [0.1.5](https://github.com/tks18/personal-finance-etl/compare/0.1.4...0.1.5) (2026-07-19)

### [0.1.4](https://github.com/tks18/personal-finance-etl/compare/0.1.3...0.1.4) (2026-07-19)


### Build System 🏗

* add logos, add pyinstaller spec file, version_info file for windows build ([0cc6db1](https://github.com/tks18/personal-finance-etl/commit/0cc6db14f50f2cd3b1053b42d8c2c30c57c4aef4))
* add scripts for build and dev tasks ([05f49ef](https://github.com/tks18/personal-finance-etl/commit/05f49ef9b83b1e1f916689757d695465170ce0e0))


### Features 🔥

* **engines/core:** write core quant operations: xirr, cagr, other metrics ([fcd5367](https://github.com/tks18/personal-finance-etl/commit/fcd53673cfc3f342e9072959b3cef713a03c3644))
* **engines/core:** write the core fifo functionality for investment tracking ([2f1e0bc](https://github.com/tks18/personal-finance-etl/commit/2f1e0bc65ae88fb9ae02beb505fd5eb40638a5fa))
* **engines/io:** handle the data preprocessing for investment tracking ([1d43769](https://github.com/tks18/personal-finance-etl/commit/1d437691d21c093434f10980740055245c7e6362))
* **engines/rules:** add core tax rules for the calculation ([93a172f](https://github.com/tks18/personal-finance-etl/commit/93a172fa16b8c1133eedd06106f3f9e5c6733a4d))
* **extract:** setup extract modules for excel and sqlite db sources ([500954a](https://github.com/tks18/personal-finance-etl/commit/500954ab609a94fae99304d25b7656c326ef7ddb))
* **settings:** setup config module for handling toml configs ([2150afd](https://github.com/tks18/personal-finance-etl/commit/2150afdad581006895a0e4df57d19a0d596d754c))
* **utils:** add helpers for polars functionality ([489d1ba](https://github.com/tks18/personal-finance-etl/commit/489d1ba5723765da380edbd8065912a62e2bbd13))
* **utils:** setup logging functionality using queue in ui ([a6479e4](https://github.com/tks18/personal-finance-etl/commit/a6479e44df92bf70c175223a7b6537a9763349fb))
* **utils:** shared dataclasses and enums for the App ([1e0a3b8](https://github.com/tks18/personal-finance-etl/commit/1e0a3b8cfc30aabd785b36be114efdb8c81cc11c))
* **utils:** theme utils for the UI ([3be7a60](https://github.com/tks18/personal-finance-etl/commit/3be7a6088e09848f6dc293664582f934dcca5ada))

### [0.1.3](https://github.com/tks18/personal-finance-etl/compare/0.1.1...0.1.3) (2026-07-19)

### [0.1.2](https://github.com/tks18/personal-finance-etl/compare/0.1.1...0.1.2) (2026-07-19)

### 0.1.1 (2026-07-19)


### Others 🔧

* **build:** update pyproject, setup configs for commitlint and changelogs ([532f64a](https://github.com/tks18/personal-finance-etl/commit/532f64acf8dd15ccea391a810d064dd06db854f5))
