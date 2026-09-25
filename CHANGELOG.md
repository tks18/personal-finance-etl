# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

### [6.4.2](https://github.com/tks18/personal-finance-etl/compare/6.4.1...6.4.2) (2026-09-25)


### Bug Fixes 🛠

* **backend/control_plane:** fix file renames broke pipelines, now truly resilient ([ddb13fb](https://github.com/tks18/personal-finance-etl/commit/ddb13fbd02e830a040143bde193b763ac615a55d))


### Features 🔥

* **backend/engines:** improve logging in backend engines ([3a25e49](https://github.com/tks18/personal-finance-etl/commit/3a25e49179a23f5d740b222a7f2a83cab104d71c))
* **backend/extract:** improve logging in extract part ([549dd0b](https://github.com/tks18/personal-finance-etl/commit/549dd0b14ec3d3dabf3d2d03162886e618e657c2))
* **backend/load:** improve logging across entire load interface ([ae406d1](https://github.com/tks18/personal-finance-etl/commit/ae406d110e53593986265d063432e4313a13cf48))
* **backend/pipeline:** improve logging across the entire pipeline ([9e3be42](https://github.com/tks18/personal-finance-etl/commit/9e3be424fe40af560f3d4911bf888752c3e46727))
* **backend/utils:** logger: integrate msecs, add datefmt ([d169274](https://github.com/tks18/personal-finance-etl/commit/d169274355608107bbe7476200ab9f654c77efa9))

### [6.4.1](https://github.com/tks18/personal-finance-etl/compare/6.4.0...6.4.1) (2026-09-25)


### Bug Fixes 🛠

* **backend/pipeline:** fix serious windows path bug due to which system failed to ingest files ([4189c46](https://github.com/tks18/personal-finance-etl/commit/4189c46c3321f1a9ab48a4f9e1b8f2ef2a6b7d82))

## [6.4.0](https://github.com/tks18/personal-finance-etl/compare/6.3.0...6.4.0) (2026-09-25)


### Bug Fixes 🛠

* **backend/load:** registry: benchmark data was missing in the bronze contractt ([3056667](https://github.com/tks18/personal-finance-etl/commit/3056667e82706f9c3dd03ec26843c88e39729b18))
* **backend/pipeline:** remove dead rules meta table from the code, now control plane handles that ([0f43982](https://github.com/tks18/personal-finance-etl/commit/0f43982c7aec866b95d79974090dbe9eed3aced2))


### Features 🔥

* **backend/control_plane:** artifact_repo: this is truly category resilient, update_identity method ([9ff7e6b](https://github.com/tks18/personal-finance-etl/commit/9ff7e6b8dea33c896ca01d81aba1d05a0d1ac6ab))
* **backend/control_plane:** file_sync: now the migrate identities are real ([c085c16](https://github.com/tks18/personal-finance-etl/commit/c085c164fe2d5bd74b4412d8ea65e049151bfe22))
* **backend/load/schema:** add schema for new data contract meta table ([fa062be](https://github.com/tks18/personal-finance-etl/commit/fa062bea6e86a571130da1a507704b3b05139025))
* **backend/load:** backup manager: this is truly enterprise grade ([2461468](https://github.com/tks18/personal-finance-etl/commit/2461468126e528e1358748fbf3ca9c8351e8a1a7))
* **backend/load:** bronze: implement migrate identity method ([9ad658a](https://github.com/tks18/personal-finance-etl/commit/9ad658a814d3f02f554dc564992e0b132417cbb1))
* **backend/load:** metadata: heal duck_db method is truly now heals duckdb ([feca1a0](https://github.com/tks18/personal-finance-etl/commit/feca1a09ef4e3fbaa36cc4cfbfa6f0754c07db20))
* **backend/load:** metadata: introduce new meta table for explicit data contracts ([ef93b03](https://github.com/tks18/personal-finance-etl/commit/ef93b0385f29cd8098a2a70604c7ec0d26b4f4bd))
* **backend/pipeline:** etl_pipeline: now the entire pipeline is disaster recoverable ([cff8fd1](https://github.com/tks18/personal-finance-etl/commit/cff8fd14e67e16e92843a23939c581af7c8ecd97))


### Styling 🎨

* lint fixes across files ([576b439](https://github.com/tks18/personal-finance-etl/commit/576b43986101165c65ed259522de308dff7fe417))


### Docs 📃

* add production hardening edge cases doc ([41ef20d](https://github.com/tks18/personal-finance-etl/commit/41ef20dd21a8648049598437530e0594d829abe7))
* mark completed against the production hardening checklist ([9cab094](https://github.com/tks18/personal-finance-etl/commit/9cab094e9bb1db889f4ce4651257e8fbe2fe4179))

## [6.3.0](https://github.com/tks18/personal-finance-etl/compare/6.2.3...6.3.0) (2026-09-25)


### Build System 🏗

* **pyproject:** add filelock as dependency ([963001f](https://github.com/tks18/personal-finance-etl/commit/963001f45ec71eb434e4fba0591e016059aad4d8))


### Bug Fixes 🛠

* **backend/engines:** isin_pipeline: handle future pool failing and handle it properly ([8df9127](https://github.com/tks18/personal-finance-etl/commit/8df912797f9e5adc0f255e4eb3e7f97b1e4d57ad))


### Code Refactoring 🖌

* **backend/load:** database: remove stale backup method ([bc4aa33](https://github.com/tks18/personal-finance-etl/commit/bc4aa330b11813276844e4d5844ba3ef54477127))
* initialize the variables for pylance ([d327c7f](https://github.com/tks18/personal-finance-etl/commit/d327c7fec445fea1f32d7795c4c0b70693bfdcd9))


### Features 🔥

* **backend/api:** use the new backup manager in the api facade ([0ee6ad6](https://github.com/tks18/personal-finance-etl/commit/0ee6ad62d212371fbeb025efbe0c3a9dd379daa5))
* **backend/control_plane:** add a recovery mode for stale runs ([8469842](https://github.com/tks18/personal-finance-etl/commit/8469842df5b66d0643dc98afd05d1b3975b05f85))
* **backend/control_plane:** file_sync: now checks for renames and updates automatically ([0fd860c](https://github.com/tks18/personal-finance-etl/commit/0fd860c6297249cb3ebf76fbcdd89a46e78db2d8))
* **backend/control_plane:** implement filelock around the main sqlite ops database ([1554821](https://github.com/tks18/personal-finance-etl/commit/1554821858f060fca3a2c14925581be5e65ad8db))
* **backend/load:** bronze: use the new data contracts in the bronze loading ([3960eb0](https://github.com/tks18/personal-finance-etl/commit/3960eb0e9e2f79ff315ee124a5872e33514c952a))
* **backend/load:** introduce backup manager that will handle backup of both sqlite + duckdb ([38fe640](https://github.com/tks18/personal-finance-etl/commit/38fe64001ae24b63b1f75c0137a15b532bba98f6))
* **backend/load:** introduce new data contract for bronze tables too ([0ee5ecb](https://github.com/tks18/personal-finance-etl/commit/0ee5ecb2fba602eb757ae365cdbdba96e109b992))
* **backend/load:** metadata: use the new bronze registry and also check the synced files properly ([554dc09](https://github.com/tks18/personal-finance-etl/commit/554dc0989261d8cf35ef951e3e184112f1527142))
* **backend/load:** registry: introduce a method to validate entire data registry ([612b722](https://github.com/tks18/personal-finance-etl/commit/612b722ae43e629fcd6726cb328a1b0a301d0fc8))
* **backend/pipeline:** etl_pipeline: production hardening changes ([9981aa2](https://github.com/tks18/personal-finance-etl/commit/9981aa2f4f1581102b9065fc7e5c98e6ad66ca7f))


### Docs 📃

* mark completed against production hardening checks ([c2099a3](https://github.com/tks18/personal-finance-etl/commit/c2099a3d94af4dd6e39dde459ec7715c5df36e0e))

### [6.2.3](https://github.com/tks18/personal-finance-etl/compare/6.2.2...6.2.3) (2026-09-25)


### Code Refactoring 🖌

* **backend/engines:** math.py remove dead dietz calculation code ([7601e77](https://github.com/tks18/personal-finance-etl/commit/7601e7790350687a067a9da7c408ceb23151a064))


### Bug Fixes 🛠

* **backend/control_plane:** fix data contracts pub order, grain ([07bcbdb](https://github.com/tks18/personal-finance-etl/commit/07bcbdb61cb62b26031f026dcf5c7c8dbe186169))
* **backend/control_plane:** fix virtual files path generation mismatch ([6cf7c1d](https://github.com/tks18/personal-finance-etl/commit/6cf7c1d952938f1e422caf4b2d2a23f36a75573d))
* **backend/engines:** investment_analytics - add subtype back to the col list ([c100944](https://github.com/tks18/personal-finance-etl/commit/c1009443ce1a18aede5da9aa6a4049ed80f67fd9))
* **backend/load:** gold - use the pub order to push to db ([3483ddc](https://github.com/tks18/personal-finance-etl/commit/3483ddc84235be7761c052803eae450262f8312d))
* **backend/load:** meta - use the datacontracts for the meta layer ([c9ea76d](https://github.com/tks18/personal-finance-etl/commit/c9ea76dfdc116747fc52045176ac438250fdabdd))
* **backend/load:** silver - use the pub order to push to db ([f899f71](https://github.com/tks18/personal-finance-etl/commit/f899f71d4541fb75952678d3c0d64be40059ad41))


### Build System 🏗

* **.versionrc.js:** remove stale version bump for docs/about.md ([51051e2](https://github.com/tks18/personal-finance-etl/commit/51051e2dbff8897fb5988803ec3b640ce93b91b0))
* consistent repo metadata across all the files in the repo ([615eff2](https://github.com/tks18/personal-finance-etl/commit/615eff2e6dd1aa2097c558a4fa541f8c09feb1d7))


### Others 🔧

* add CONTRIBUTING.md file ([297447f](https://github.com/tks18/personal-finance-etl/commit/297447febb7c3ead22cc4b6500125b89e890efae))
* add issue templates file ([4c758a8](https://github.com/tks18/personal-finance-etl/commit/4c758a8cbe2986fa1d2db824ad7e3e1f62599628))
* add pull request template file ([4953636](https://github.com/tks18/personal-finance-etl/commit/4953636fe27efa54783ae26e3280112d6aaa5bad))
* add SECURITY.md file ([84b291d](https://github.com/tks18/personal-finance-etl/commit/84b291d3f82e133da7efe84358bf55864f194081))


### Docs 📃

* add production hardening edge cases doc ([c9c6f9a](https://github.com/tks18/personal-finance-etl/commit/c9c6f9a08019c71d76f3d01c1299c1383e0eeac6))
* fix logo link for pypi scenarios ([7849c1b](https://github.com/tks18/personal-finance-etl/commit/7849c1b3df5654ffcda54f2f2853865c9bc3aefa))
* fix math formulas not rendering properly ([f245ec9](https://github.com/tks18/personal-finance-etl/commit/f245ec940023aac7470ee1eb4ac42f0ef4058f25))
* link main readme to wiki ([4e74cdc](https://github.com/tks18/personal-finance-etl/commit/4e74cdc77c22203061afe9723e342046c7a00310))
* link tech docs readme to wiki ([4a29389](https://github.com/tks18/personal-finance-etl/commit/4a2938921ff810ccee133c3ab8f08b903fa782ca))
* minor wording changes ([ade0ffa](https://github.com/tks18/personal-finance-etl/commit/ade0ffa136584545845ce8dfd78fa87e3c11d12a))
* **readme:** update readme after the recent architecture refactor ([62b2cdc](https://github.com/tks18/personal-finance-etl/commit/62b2cdca1553161005f3b5fd10da82ec8b5e9c48))
* refactor about docs to reflect recent changes ([6fe32f6](https://github.com/tks18/personal-finance-etl/commit/6fe32f6df9d807c643ac711c70de7104af475448))
* refactor architecture docs to reflect recent changes ([fe0a325](https://github.com/tks18/personal-finance-etl/commit/fe0a325502950103a678440132759266d871c66d))
* refactor configuration docs to reflect recent changes ([c3abec2](https://github.com/tks18/personal-finance-etl/commit/c3abec271b11259cee8d262d6bb6b1f4cb7c3874))
* refactor developer docs to reflect recent changes ([f34db04](https://github.com/tks18/personal-finance-etl/commit/f34db04c811819b4b690d762d4f49c83fded6e7c))
* refactor finance docs to reflect recent changes ([3b02edd](https://github.com/tks18/personal-finance-etl/commit/3b02edd7b262d164f2b911ba5bc44e5c9829f9cc))
* refactor getting started docs to reflect recent changes ([c2897b4](https://github.com/tks18/personal-finance-etl/commit/c2897b4d12b789d4ed2b2ab0eed1580b68fbdedd))
* refactor reference docs to reflect recent changes ([6ab656d](https://github.com/tks18/personal-finance-etl/commit/6ab656d9c58369b3f8936cb568f62a297f5d9278))
* update all sub folder base readme file ([c5d7aac](https://github.com/tks18/personal-finance-etl/commit/c5d7aacc08eb467bb7f402f849ec40847e02193b))
* update base docs readme file ([092bcff](https://github.com/tks18/personal-finance-etl/commit/092bcff6e652c61b4a43fa43fffd702bd4d6e3ff))
* update manifest, remove legacy docs in manifest ([4bf957c](https://github.com/tks18/personal-finance-etl/commit/4bf957c032992bfbbd7a71f8d7e2daa4dc0a9b7c))


### Styling 🎨

* lint fixes ([a6a6cee](https://github.com/tks18/personal-finance-etl/commit/a6a6cee4eeab3ff931ebdc9d28e09d0ab0e87699))

### [6.2.2](https://github.com/tks18/personal-finance-etl/compare/6.2.1...6.2.2) (2026-09-25)


### Performance Improvements 🏎

* **backend/engines:** math: remove dead code ([1c42789](https://github.com/tks18/personal-finance-etl/commit/1c427892b7babd266dd481ea81809b2c5aa97016))
* **backend/engines:** persentation: remove risk metrics dead code, improving model perf ([afe2ef7](https://github.com/tks18/personal-finance-etl/commit/afe2ef7ee128ac839a9393bd1434942bdc2f140d))
* **backend/engines:** quant: remove risk metrics dead code, improving perf ([3300997](https://github.com/tks18/personal-finance-etl/commit/330099723891ef322e4c0be422358a3800ed0eed))


### Code Refactoring 🖌

* remove risk metrics from main presentation dag ([b3b50d3](https://github.com/tks18/personal-finance-etl/commit/b3b50d3c334da497991fc4fa1f1df15ac565fb70))


### Styling 🎨

* linting fixes across files ([6a8d699](https://github.com/tks18/personal-finance-etl/commit/6a8d6990815972a417bc7d2d46a0c1354a146332))
* remove legacy comments ([89a6950](https://github.com/tks18/personal-finance-etl/commit/89a6950c762bb1b6f24fd7d6ebd68e63498cbff0))


### Docs 📃

* update doc strings in main __init__.py files ([1ba0568](https://github.com/tks18/personal-finance-etl/commit/1ba056850fe092d4db9e81330047eb17d264afac))

### [6.2.1](https://github.com/tks18/personal-finance-etl/compare/6.2.0...6.2.1) (2026-09-24)


### CI 🛠

* **pyproject:** change changelog link ([915ec82](https://github.com/tks18/personal-finance-etl/commit/915ec829150897bc9c29f863915f3e7910cb5ae8))

## [6.2.0](https://github.com/tks18/personal-finance-etl/compare/6.1.1...6.2.0) (2026-09-24)


### Styling 🎨

* auto lint commit ([a9888b5](https://github.com/tks18/personal-finance-etl/commit/a9888b587b273dfc112c9de7e14f0bcf5ac54fb8))


### Bug Fixes 🛠

* **backend/engines:** remove print statements, route it through logger only ([2eb7db2](https://github.com/tks18/personal-finance-etl/commit/2eb7db2c8f2b5c762722571562f80b7eede9842a))
* **backend/gold:** fix isin pipeline ignoring errors now properly routes through traceback logs ([ed80c2a](https://github.com/tks18/personal-finance-etl/commit/ed80c2ad208718fd5557c43abca07cf7824a4531))
* **backend/gold:** remove unused metrics calculation from dag ([1321c83](https://github.com/tks18/personal-finance-etl/commit/1321c83a466a2fbf71270b2c26aaf37bd1321890))


### Others 🔧

* **backend/control_plane:** export single facade orchestrator ([cdda01f](https://github.com/tks18/personal-finance-etl/commit/cdda01f7cb6b415d7ef13786f59f07917338db44))


### Features 🔥

* **backend/config:** outsource portfolio mgmt related params ([e9c036a](https://github.com/tks18/personal-finance-etl/commit/e9c036aae4bf4d62f9df5a12b92d634003ac1b6f))
* **backend/config:** use the new outsourced portfolio param in calculation ([ad0b90e](https://github.com/tks18/personal-finance-etl/commit/ad0b90e4c3255bdfb6cfd1e111a5bf210a38491f))
* **backend/control_plane:** add schema for new control plane tables ([d804ec7](https://github.com/tks18/personal-finance-etl/commit/d804ec78ac157f1ac99ad43d5346a7d09bdd63b9))
* **backend/control_plane:** facade for entire control plane operations through dep injection ([223d25e](https://github.com/tks18/personal-finance-etl/commit/223d25eadc6a901e93a5440725fff06d852e07da))
* **backend/control_plane:** file syncing service for control plane ([ce0d52b](https://github.com/tks18/personal-finance-etl/commit/ce0d52b1d459f67f601562fd460bf4dce5d56bfe))
* **backend/control_plane:** run time tracking service for control plane ([e9847c7](https://github.com/tks18/personal-finance-etl/commit/e9847c7a483cf15296841a8ee065359e2938b898))
* **backend/control_plane:** sqlite manager for control plane ([edb78c7](https://github.com/tks18/personal-finance-etl/commit/edb78c7cf03c95c37313d140d452eccad9e457eb))
* **backend/control_plane:** write artifact_repo class to handle file registry ([62303b3](https://github.com/tks18/personal-finance-etl/commit/62303b38955b377cb8de76cc385ffa16e55b4fb5))
* **backend/control_plane:** write common utils in control plane ([27fe751](https://github.com/tks18/personal-finance-etl/commit/27fe7515379f304f8794aee7edaeb242d6597900))
* **backend/load:** create datacontracts that defines the coded tables -> layer -> db tables ([fde8642](https://github.com/tks18/personal-finance-etl/commit/fde8642ee647a698f607875a5deec6590efd092c))
* **backend/load:** metadata: completely rewrite to recreate a lean meta structure for duckdb ([fc5d491](https://github.com/tks18/personal-finance-etl/commit/fc5d491268624f17435ab3acb61dad24588d52fd))
* **backend/pipeline:** orchestrate the entire pipeline with control plane, duckdb meta layers ([d97fbc5](https://github.com/tks18/personal-finance-etl/commit/d97fbc5c8f0298ccca2200f4e036827f63ecb905))
* **backend/schema:** refactor / make the duckdb meta layer lean ([7413d8a](https://github.com/tks18/personal-finance-etl/commit/7413d8a70ab87b74edfbd2fa798fc9cd922f4dd6))
* **backend/utils:** logger: small function to close connections ([61d975c](https://github.com/tks18/personal-finance-etl/commit/61d975c133bdad7c79e82405f68f57f695ddbd0c))
* **frontend/commons:** create a common md renderer function ([f8a353c](https://github.com/tks18/personal-finance-etl/commit/f8a353c1a7638bb9f37baaa0852143329a8a539e))
* **frontend/commons:** create a docs manifest parser module ([857244d](https://github.com/tks18/personal-finance-etl/commit/857244d59960f74006e5865a53e127687a022e6a))
* **frontend/commons:** create new guides window with the new manifest ([afc884a](https://github.com/tks18/personal-finance-etl/commit/afc884a8002458089fb63ce46172cf0f0535920a))


### Code Refactoring 🖌

* **backend/extract:** refactor to use control plane ([47945b8](https://github.com/tks18/personal-finance-etl/commit/47945b83f4b7e34e77998b74b734a327fd94e5a9))
* **backend/gold:** rename col in investment analytics to reflect calc nature ([02191cc](https://github.com/tks18/personal-finance-etl/commit/02191ccba68f8f915e746f8f9e2a9d2c09f407cb))
* **backend/gold:** rename col in portfolio analytics to reflect actual calc nature ([56dba72](https://github.com/tks18/personal-finance-etl/commit/56dba72dd8112ae9238fe2e94e86eb5f753b0304))
* **backend/load:** bronze: refactor to use control plane ([5cde29b](https://github.com/tks18/personal-finance-etl/commit/5cde29bafcb47a189c6b3fe48751d9f10fe96949))
* **backend/load:** gold: use data contracts instead of manual table mappings ([8d9bc95](https://github.com/tks18/personal-finance-etl/commit/8d9bc95f97f8ca4deedc5ed60fd65caf1c5534ff))
* **backend/load:** remove file tracker, control plane replaces it fully ([b5e9641](https://github.com/tks18/personal-finance-etl/commit/b5e9641180329b5a687f7a2040a1b4fcb69b6488))
* **backend/load:** remove legacy raw.py, control plane properly replaces it on all terms ([ff188a9](https://github.com/tks18/personal-finance-etl/commit/ff188a937b1c779e9dfd5cb074e3caf81875a3cd))
* **backend/load:** silver: use data contracts instead of manual table mappings ([60aeb43](https://github.com/tks18/personal-finance-etl/commit/60aeb439b99763856056ab8931bb478c3d8fc8a0))
* **backend/pipeline:** benchmark: refactor to use control plane ([9a9f9de](https://github.com/tks18/personal-finance-etl/commit/9a9f9de25899407856bce4e540271069332531cb))
* **backend/pipeline:** control plane refactor ([895787f](https://github.com/tks18/personal-finance-etl/commit/895787fe949ad0373a7c0ee9bbb533c88629a7b3))
* **frontend:** use the new docs renderer across cli, gui ([e957258](https://github.com/tks18/personal-finance-etl/commit/e95725860f50bf8f08ee252e2c10db2f358fc561))


### Docs 📃

* add about-me doc ([8aa3c74](https://github.com/tks18/personal-finance-etl/commit/8aa3c746a4ec95ab5765f8b966f767086d99b91d))
* add about/project.md ([a915293](https://github.com/tks18/personal-finance-etl/commit/a915293f5a47e3a0dff89a5dcdf3638bb0512432))
* add architecture/data-lifecycle.md ([ccb63ee](https://github.com/tks18/personal-finance-etl/commit/ccb63eef636845255f3dfd71c6df62abce15853b))
* add architecture/system-architecture.md ([87141af](https://github.com/tks18/personal-finance-etl/commit/87141afb277c50deb3dff1a0d230c3b45b31750f))
* add architecture/warehouse-architecture.md ([9bad446](https://github.com/tks18/personal-finance-etl/commit/9bad44688bca9b6c70362ec213ac51bf8fa84156))
* add base readme for each docs subfolder replacing _.md ([479d3dd](https://github.com/tks18/personal-finance-etl/commit/479d3dd151b6707a4a08d031ad59007ee9d69538))
* add configuration docs ([8b4229c](https://github.com/tks18/personal-finance-etl/commit/8b4229ca1613ef67d23b40bf74d68c2e739494d4))
* add developer docs ([a246b03](https://github.com/tks18/personal-finance-etl/commit/a246b0380ed8691389e5f79c40e74f7008aef2a5))
* add finance docs ([27d5dc5](https://github.com/tks18/personal-finance-etl/commit/27d5dc529dd48d301c4d7424346dcad70fe224cb))
* add getting-started docs ([77ab30f](https://github.com/tks18/personal-finance-etl/commit/77ab30fa986a27f350b2b12ead38f068044b5ccd))
* add navigation docs base readme ([8802327](https://github.com/tks18/personal-finance-etl/commit/8802327b628142817912a92bed56336ffa1bdf6f))
* add production hardening checklist ([d9c3a7e](https://github.com/tks18/personal-finance-etl/commit/d9c3a7e1e66b8a149eaf28c346d72ec3318bbb83))
* add reference docs ([7d081ae](https://github.com/tks18/personal-finance-etl/commit/7d081ae58a823a5e915b359c1d1c62011293e335))
* add remaining architecture docs ([273794d](https://github.com/tks18/personal-finance-etl/commit/273794db47204dfa44a263d301e624eb7f277c15))
* add roadmap for the project ([4cffa24](https://github.com/tks18/personal-finance-etl/commit/4cffa249953756326182c58c3b107370dd797275))
* **docs/legacy:** remove all legacy doc files ([3c3e18a](https://github.com/tks18/personal-finance-etl/commit/3c3e18a5bdb903fd8e97cbc55fd6df7b04e484fa))
* **docs/manifest.json:** create a manifest file for docs rendering across cli, gui ([1ebd75c](https://github.com/tks18/personal-finance-etl/commit/1ebd75c3f77a63802d9531a773c451d52145029a))
* establish documentation structure and archive legacy guides ([aca6f1b](https://github.com/tks18/personal-finance-etl/commit/aca6f1be109947a3475119639a9fcc3afc498fcf))
* **financial_rules:** add the new parameters to sample config ([75a7151](https://github.com/tks18/personal-finance-etl/commit/75a7151b98c9d145c1850158a426db50fee38897))
* minor content updates ([ea2adba](https://github.com/tks18/personal-finance-etl/commit/ea2adbaabde11c3ecf65b25f94142cf63be2209b))
* minor updates to docs/about/readme ([8f71379](https://github.com/tks18/personal-finance-etl/commit/8f71379d4f96775396088405f19edfaa321139ba))
* minor updates to docs/about/roadmpa ([7cf3381](https://github.com/tks18/personal-finance-etl/commit/7cf338154befaf32f57d46df73a3a7a416e7ffe2))
* minor updates to docs/readme ([375504b](https://github.com/tks18/personal-finance-etl/commit/375504b7cf0a2675d99484e9261110e9a9021659))
* **readme.md:** add code quality badge ([374e99c](https://github.com/tks18/personal-finance-etl/commit/374e99c91d55af9cc313a8413eddf340b40d15fc))
* **readme.md:** completely rewrite readme to reflect the true nature of the project instead of ai slopped readme ([3d59eb3](https://github.com/tks18/personal-finance-etl/commit/3d59eb3182d8710ac1c9ae98172b45bea2b52f2e))
* **readme.md:** update few badges ([7ebce40](https://github.com/tks18/personal-finance-etl/commit/7ebce405ce78f4a958b4270b493972054994e58a))
* update readme to refer docs structure ([8bd60c2](https://github.com/tks18/personal-finance-etl/commit/8bd60c20bbf03bb452b415c745cf8bfad68ca3d1))


### Build System 🏗

* **pyinstaller:** update main.spec to include docs manifest ([bbe9b86](https://github.com/tks18/personal-finance-etl/commit/bbe9b8684b709ae5c9830084ca0025bf3f0ea8b1))
* **pypi:** add docs manifest to the pypi build ([3ae5473](https://github.com/tks18/personal-finance-etl/commit/3ae5473b75346dae76e618c4121a336e7e311921))

### [6.1.1](https://github.com/tks18/personal-finance-etl/compare/6.1.0...6.1.1) (2026-09-23)


### Bug Fixes 🛠

* **backend/pipeline:** keep the file registry in sync (missed benchmark in duckdb registry) ([d9c1780](https://github.com/tks18/personal-finance-etl/commit/d9c178058b3f38ed352ea7ed09ba7eb5d8ddab0e))
* **backend/raw:** fix full replacement datasets being unnecessarily stored in raw store ([1a755b8](https://github.com/tks18/personal-finance-etl/commit/1a755b8717c9f665130fde8e3795c8806883b0b3))


### Features 🔥

* **backend/load:** make raw store the primary source of truth for actionable files ([aa55dbe](https://github.com/tks18/personal-finance-etl/commit/aa55dbe25ab469667a4a04a83389fc60733677a4))
* **backend/pipeline:** now just simply call the api to find actionable files ([aea882e](https://github.com/tks18/personal-finance-etl/commit/aea882e63597267423ef10e4405bd1b661836630))

## [6.1.0](https://github.com/tks18/personal-finance-etl/compare/6.0.1...6.1.0) (2026-09-23)

### [6.0.1](https://github.com/tks18/personal-finance-etl/compare/6.0.0...6.0.1) (2026-09-23)


### Build System 🏗

* **main.spec:** update build spec to remove all adbc line items ([8e2fd4f](https://github.com/tks18/personal-finance-etl/commit/8e2fd4f5b554342f4450671276194c2b5ae171b4))
* remove adbc driver dependency ([769dcb6](https://github.com/tks18/personal-finance-etl/commit/769dcb6bb0826c09331d9c01bcb8a438c66e63c1))


### Code Refactoring 🖌

* **engine/benchmark:** move the benchmark p'ing to transform folder for srp ([e56e2a1](https://github.com/tks18/personal-finance-etl/commit/e56e2a17f981382a4ad4fc2ca4dda3266287f54b))
* **engines/benchmark:** move the benchmark fetcher to extract folder for proper srp ([a755c40](https://github.com/tks18/personal-finance-etl/commit/a755c404d14e74670a0bbdc31ff6542d54751b6d))
* minor refactors and renames ([f0a52dd](https://github.com/tks18/personal-finance-etl/commit/f0a52ddbc0160bc9beda07a00039019ee86d5996))


### Features 🔥

* **backend/config:** make raw store mandatory, add a flag for new file discovery ([558fb4c](https://github.com/tks18/personal-finance-etl/commit/558fb4c00a26b87ffd9c48e98a28e1f32a354815))
* **backend/extract:** convert csv extractors to process io bytes ([fed9474](https://github.com/tks18/personal-finance-etl/commit/fed947424f9d26d3a06fbeee72ba1fc72e1a91b3))
* **backend/extract:** convert excel extractors to process io bytes ([09c1717](https://github.com/tks18/personal-finance-etl/commit/09c17176608e63569ff3d8e1697ac8e0fe2f4f4c))
* **backend/extract:** sqlite: remove adbc, convert/implement memory stream processing ([7a3d1ad](https://github.com/tks18/personal-finance-etl/commit/7a3d1adfe1117991be1bc19f67df3b9f59da0879))
* **backend/load:** file_tracker: use raw store methods and raw store file registry to handle ([0c8fb85](https://github.com/tks18/personal-finance-etl/commit/0c8fb852caedd9a634ad88df6f15e38d2d4d8977))
* **backend/load:** raw: make raw store the primary file tracker rather than duckdb registry ([33a7611](https://github.com/tks18/personal-finance-etl/commit/33a76117c4796843d59f42f74bd48d3f3744bebd))
* **backend/pipeline:** make the extractor now process raw bytes instead of file paths and os items ([150994c](https://github.com/tks18/personal-finance-etl/commit/150994c260f749d2d13b84d55c8f8874a13ce9a5))
* **backend/pipeline:** move benchmark to pipeline ([08438c0](https://github.com/tks18/personal-finance-etl/commit/08438c0b27d6703bd129ef0a839130afb60e3920))
* **backend/pipeline:** now orchestrate the entire raw store -> gold pipeline ([d719e17](https://github.com/tks18/personal-finance-etl/commit/d719e17b1e2e1075634e5fd23f144989845eb943))


### Docs 📃

* **readme, about:** update both readme and about to reflect recent changes ([f87201b](https://github.com/tks18/personal-finance-etl/commit/f87201b9ad6f75ad6b0140844f1ea2b09ce7fbad))

## [6.0.0](https://github.com/tks18/personal-finance-etl/compare/5.9.1...6.0.0) (2026-09-22)


### Code Refactoring 🖌

* move mf mapping, currency to fin_rules as this is a transactional config ([10bf852](https://github.com/tks18/personal-finance-etl/commit/10bf8524775200739d00d95b03cf33983e347889))


### Features 🔥

* **backend/load:** add uuid for file hasher for unique doc ids ([76ca211](https://github.com/tks18/personal-finance-etl/commit/76ca21100c4518d5af99613e0451b71cf04de88c))
* **backend/load:** implement raw document store using the existing file hasher as base ([86c548d](https://github.com/tks18/personal-finance-etl/commit/86c548d5364694bb8be289c309eb241062a38344))
* **backend/pipeline:** orchestrate the entire raw store in the existing plan ([a4a8e39](https://github.com/tks18/personal-finance-etl/commit/a4a8e3947ee0a26e6d581e61463c682183f9a303))
* **backend/settings:** implement config for raw landing stage which will store raw file bytes ([630bd04](https://github.com/tks18/personal-finance-etl/commit/630bd04a3a9d65dc1d6fb319317fa6e695319911))


### Build System 🏗

* add uuid to package ([2c9eaa5](https://github.com/tks18/personal-finance-etl/commit/2c9eaa56709177deb6c11314932acdb63d3d8707))

### [5.9.1](https://github.com/tks18/personal-finance-etl/compare/5.9.0...5.9.1) (2026-09-21)


### Bug Fixes 🛠

* **backend/gold:** fix total assets not included liabilities ([f946f2f](https://github.com/tks18/personal-finance-etl/commit/f946f2fb7bc3cf5426d77b6323ee2a878c0666f2))

## [5.9.0](https://github.com/tks18/personal-finance-etl/compare/5.8.2...5.9.0) (2026-09-21)


### Features 🔥

* **backend/config:** add new config for configuring non cash incomes ([e28b990](https://github.com/tks18/personal-finance-etl/commit/e28b990d48b5ff376591569c79bade5b76f69e17))
* **backend/ddl:** update gold ddl tables ([949d781](https://github.com/tks18/personal-finance-etl/commit/949d78156462334117c8d0fedc86851e2a7029cd))
* **backend/gold:** update all gold layer tables to implement the cash income for analytics ([72662fd](https://github.com/tks18/personal-finance-etl/commit/72662fdb64bf696b0fc43a8811ccff86d0c1674d))
* **backend/gold:** update core processing to bifurcate income type to cash/non-cash ([3ca1849](https://github.com/tks18/personal-finance-etl/commit/3ca184940fb22faf72ae24bb6f94134e2b2bba90))
* **backend/transform:** add the new dimension to income cat and sub cat tables ([5f3fe84](https://github.com/tks18/personal-finance-etl/commit/5f3fe845c738a0e8fc0d3f0e5d9df538e2abf87d))


### Docs 📃

* add sample config for rules ([693686c](https://github.com/tks18/personal-finance-etl/commit/693686c2a6d9501190eedaf427e54c297642856f))

### [5.8.2](https://github.com/tks18/personal-finance-etl/compare/5.8.1...5.8.2) (2026-09-20)


### Features 🔥

* **backend/gold:** add avg investment rate to cashflow efficiency table ([db05774](https://github.com/tks18/personal-finance-etl/commit/db057744ecb822917ce9e8a69295b71687d29b9c))

### [5.8.1](https://github.com/tks18/personal-finance-etl/compare/5.8.0...5.8.1) (2026-09-20)


### Bug Fixes 🛠

* **backend/gold:** add more helper cols to cashflow_efficiency_table ([dbdaa0a](https://github.com/tks18/personal-finance-etl/commit/dbdaa0abddd3e8cae266dd08f8560b0918216d1f))
* **backend/gold:** fix cashflow summary reporting inconsistent cash expenses ([6998f51](https://github.com/tks18/personal-finance-etl/commit/6998f516967cdb0c0537c3f52b211e2fa3b2096e))

## [5.8.0](https://github.com/tks18/personal-finance-etl/compare/5.7.0...5.8.0) (2026-09-20)


### CI 🛠

* **versionrc:** update versionrc.js file to auto update version in about.md ([709ab63](https://github.com/tks18/personal-finance-etl/commit/709ab634bb8ffdab03b4f6392e5e301f4e524197))


### Build System 🏗

* add markdown, pywebview packages, update pyproject.toml ([4fa4a09](https://github.com/tks18/personal-finance-etl/commit/4fa4a09c39e73ad9dea073ddbe0a4756aac38834))
* **main.spec:** add additional docs to include in the build spec for pyinstaller ([3b9648f](https://github.com/tks18/personal-finance-etl/commit/3b9648fa62c27765d8be6de04eb615fd2d2f02d3))


### Docs 📃

* **about.md:** add a short about.md for introduction ([64efc01](https://github.com/tks18/personal-finance-etl/commit/64efc0155f3073d0e18672167e66cb88f582a133))
* **readme:** update note in readme ([7f551eb](https://github.com/tks18/personal-finance-etl/commit/7f551eb95584d6fc72f1b2ed8a1474af4259d9b0))
* update docs guides ([ced59bf](https://github.com/tks18/personal-finance-etl/commit/ced59bf99cd56339868855e2927be6eb86f031dc))
* update readme, other guides in docs folder ([8460f1b](https://github.com/tks18/personal-finance-etl/commit/8460f1b056e895ac1d7a4cded827a2c891dc8bed))


### Features 🔥

* **frontend/docs:** create a simple webview module for docs rendering ([5580a0f](https://github.com/tks18/personal-finance-etl/commit/5580a0f97f9de0bede2cf48d4b852ca8a81f21e5))
* **frontend:** add docs options to both cli and gui ([62e0bc2](https://github.com/tks18/personal-finance-etl/commit/62e0bc22b359595990debbd8c4c1a30b2aff2a7e))
* **helpers:** update to add helpers for docs file identifications on build ([9ea9565](https://github.com/tks18/personal-finance-etl/commit/9ea95659d344eb9d6926ecfddb872f1c22cb23c7))

## [5.7.0](https://github.com/tks18/personal-finance-etl/compare/5.6.0...5.7.0) (2026-09-17)


### Features 🔥

* **backend/config:** add new configs for cashflow management ([edc9374](https://github.com/tks18/personal-finance-etl/commit/edc93744aa517af085d442a9421dea85e7e6905e))
* **backend/db:** add new dims to the schema ([323eb07](https://github.com/tks18/personal-finance-etl/commit/323eb07aa3bf760fa4625a659583dea4f9d4ebdd))
* **backend/db:** add schema for new table ([f40989a](https://github.com/tks18/personal-finance-etl/commit/f40989aebb7d82f1483f81577bf2f8fccbc64588))
* **backend/gold:** add new cashflow metrics ([c25c0ec](https://github.com/tks18/personal-finance-etl/commit/c25c0ec8d2ad322da1c7d91e70d471a83b0d5ccf))
* **backend/gold:** add various metrics using cashflow related dim ([6462ae0](https://github.com/tks18/personal-finance-etl/commit/6462ae06443c2b1e8e20353a0abb7f432fdbef99))
* **backend/gold:** new table for cashflow statement ([a47326b](https://github.com/tks18/personal-finance-etl/commit/a47326b218faf7d9322b6ab044d2b22f44281ae0))
* **backend/transform:** update method to add dims for cashflow management ([cd3ee84](https://github.com/tks18/personal-finance-etl/commit/cd3ee84bee872127cea5d7c2a7933bfda27e6cfd))


### Docs 📃

* add sample config ([be8f541](https://github.com/tks18/personal-finance-etl/commit/be8f5414734c7c34b6b48cdd9cb3163820c77084))

## [5.6.0](https://github.com/tks18/personal-finance-etl/compare/5.5.0...5.6.0) (2026-09-10)


### Bug Fixes 🛠

* fix sort bug due to which month elapsed was wrong ([2a355e5](https://github.com/tks18/personal-finance-etl/commit/2a355e517a1587a4e04ecbbc6134ec99df762334))


### Features 🔥

* **db/gold:** add two cols to investment tables: total stocks and total quantity for agg tables ([9144111](https://github.com/tks18/personal-finance-etl/commit/9144111187f6491913986134a7656957ce36df3f))

## [5.5.0](https://github.com/tks18/personal-finance-etl/compare/5.4.0...5.5.0) (2026-09-10)


### Features 🔥

* **db/gold:** add two essential columns related to investments ([83c763b](https://github.com/tks18/personal-finance-etl/commit/83c763b6e97328b6b38f0b02c2abd6274cbeb20a))

## [5.4.0](https://github.com/tks18/personal-finance-etl/compare/5.3.0...5.4.0) (2026-09-09)


### Bug Fixes 🛠

* reorganize the gold layer structure ([552a4f2](https://github.com/tks18/personal-finance-etl/commit/552a4f2f77252788c04ba305fcd10bb819112a64))

## [5.3.0](https://github.com/tks18/personal-finance-etl/compare/5.2.0...5.3.0) (2026-09-08)


### Bug Fixes 🛠

* more overkill columns removal ([17a6565](https://github.com/tks18/personal-finance-etl/commit/17a65658b92f7b5a13e7e1f32aa47f6efa1a3781))

## [5.2.0](https://github.com/tks18/personal-finance-etl/compare/5.1.4...5.2.0) (2026-09-07)


### Bug Fixes 🛠

* fix all bloatware columns completely ([490a516](https://github.com/tks18/personal-finance-etl/commit/490a5168628d0af8bf3775a121bebabe41f42daf))

### [5.1.4](https://github.com/tks18/personal-finance-etl/compare/5.1.3...5.1.4) (2026-08-21)


### Code Refactoring 🖌

* **load/schema:** update table names for proper organization ([88d96ae](https://github.com/tks18/personal-finance-etl/commit/88d96ae25b90b3b37a5b96ee68cf1266ef772b4c))
* remove spaces in cols:refactor across all the files ([09287a7](https://github.com/tks18/personal-finance-etl/commit/09287a7e5be4a9fa1a8c268a28e9b05c9ecf8fa0))


### Features 🔥

* **transform:** enhance calendar dimension for great slicing / dicing of data ([02c5d32](https://github.com/tks18/personal-finance-etl/commit/02c5d32eba51d6316566af112d9d95694f4e1255))

### [5.1.3](https://github.com/tks18/personal-finance-etl/compare/5.1.2...5.1.3) (2026-08-20)


### Bug Fixes 🛠

* schema fix ([aa0aa35](https://github.com/tks18/personal-finance-etl/commit/aa0aa3572d085cceda27f6261c1320fdb4b69168))

### [5.1.2](https://github.com/tks18/personal-finance-etl/compare/5.1.1...5.1.2) (2026-08-20)


### Bug Fixes 🛠

* **load/schema:** schema duplication fix ([faad6ee](https://github.com/tks18/personal-finance-etl/commit/faad6ee5cbce75a158aeb4007a168d8bf806e410))

### [5.1.1](https://github.com/tks18/personal-finance-etl/compare/5.1.0...5.1.1) (2026-08-20)


### Bug Fixes 🛠

* **load/schema:** schema duplication issue ([8aa741e](https://github.com/tks18/personal-finance-etl/commit/8aa741efea535c4e1d54b46994f46bf34934a452))

## [5.1.0](https://github.com/tks18/personal-finance-etl/compare/5.0.6...5.1.0) (2026-08-19)


### Styling 🎨

* linter fixes ([b9a82f6](https://github.com/tks18/personal-finance-etl/commit/b9a82f68dfa8740933ac55ff0a67eb78d0c8b477))
* renaming some table names ([48a503b](https://github.com/tks18/personal-finance-etl/commit/48a503b1ba034699884098113fb20d80775feda0))


### Features 🔥

* **engines/analytics:** implement twr, time horizon analytics in investment analytics ([3bd6402](https://github.com/tks18/personal-finance-etl/commit/3bd640239b3a4007924d138b00d91655ab4a04e3))

### [5.0.6](https://github.com/tks18/personal-finance-etl/compare/5.0.5...5.0.6) (2026-08-16)


### Bug Fixes 🛠

* **backend/engine:** fix risk metrics ([5ba3de9](https://github.com/tks18/personal-finance-etl/commit/5ba3de9bf667241bb1694e54be711282a8091947))
* **backend/engine:** fix risk metrics ([fcf9b71](https://github.com/tks18/personal-finance-etl/commit/fcf9b717c56bfcc96f7598577df4b6227ec9f321))
* **backend/engine:** fix risk metrics calculation anomaly ([77f99db](https://github.com/tks18/personal-finance-etl/commit/77f99db9f6c06ea0c07cd7c023d382c174eaaafe))

### [5.0.5](https://github.com/tks18/personal-finance-etl/compare/5.0.4...5.0.5) (2026-08-16)


### Code Refactoring 🖌

* **backend/extract:** refactor log message ([6c5bea1](https://github.com/tks18/personal-finance-etl/commit/6c5bea1274b96af37211fb070cce88bd545e99bd))


### Bug Fixes 🛠

* **frontend/cli:** escape [] blocks in rich console ([4203f41](https://github.com/tks18/personal-finance-etl/commit/4203f41d66c34110c02b6fa1bfd6f2b3c2c8e8ad))

### [5.0.4](https://github.com/tks18/personal-finance-etl/compare/5.0.3...5.0.4) (2026-08-16)


### Tests 🧪

* update cron script ([f4aac7a](https://github.com/tks18/personal-finance-etl/commit/f4aac7ac9d252c97b7cd2329db9b08ce84a11854))

### [5.0.3](https://github.com/tks18/personal-finance-etl/compare/5.0.2...5.0.3) (2026-08-16)


### Features 🔥

* **frontend/cli:** improve logging, support for auto + cron mode ([4257d68](https://github.com/tks18/personal-finance-etl/commit/4257d68d8124ef6b804e5979537e438ae75167b9))
* **frontend/cli:** support for auto + cron mode for headless run ([ace159f](https://github.com/tks18/personal-finance-etl/commit/ace159f226d9cb2adbb02105aa8ecf642febfe6c))


### Tests 🧪

* **run_pipeline:** add cron script to run pipeline headless ([f0fcad3](https://github.com/tks18/personal-finance-etl/commit/f0fcad354bdca2c4fe031113d0a8f81ad31a2417))

### [5.0.2](https://github.com/tks18/personal-finance-etl/compare/5.0.1...5.0.2) (2026-08-16)


### Build System 🏗

* **main.spec:** update spec to exclude more test libraries to reduce size ([7da1ace](https://github.com/tks18/personal-finance-etl/commit/7da1aceb2870c026e980e498c1b958c16f80544c))

### [5.0.1](https://github.com/tks18/personal-finance-etl/compare/5.0.0...5.0.1) (2026-08-15)


### Styling 🎨

* **frontend/cli:** automatically get the version ([23611eb](https://github.com/tks18/personal-finance-etl/commit/23611eb89a3e70ec081543ca85566fdf528e924d))


### Bug Fixes 🛠

* **.versionrc.js:** fix the path to __init__.py file ([af980c0](https://github.com/tks18/personal-finance-etl/commit/af980c0e015f370a561dcf0d2c254440ddeae6f1))

## [5.0.0](https://github.com/tks18/personal-finance-etl/compare/4.3.0...5.0.0) (2026-08-15)


### Features 🔥

* **backend/api:** create a backend facade api for the entire pipeline ([033e135](https://github.com/tks18/personal-finance-etl/commit/033e1350a9bed55b0e6663b0275600068f0fcadb))
* **frontend/cli:** introduce new frontend for gui less pipelines ([6c9aa56](https://github.com/tks18/personal-finance-etl/commit/6c9aa56f6248ca5cd113fde42193235eaaea24d9))


### Code Refactoring 🖌

* move backend modules to backend/*, ui modules to frontend/desktop/* ([fe1a195](https://github.com/tks18/personal-finance-etl/commit/fe1a195c90a1155f0a4a6f8b060f8d84d3c41589))
* refactor to a package based folder structure for publishing ([2416c02](https://github.com/tks18/personal-finance-etl/commit/2416c0298ff6871e2f72a832dd08775637cc062c))
* use the new module for starting the app ([f45cfc2](https://github.com/tks18/personal-finance-etl/commit/f45cfc2bdaa563517517e7d90771d258136fac08))


### Build System 🏗

* add build configs ([19e9951](https://github.com/tks18/personal-finance-etl/commit/19e9951abf3557ed2ac304337c570ec28d5b3fb1))
* update build spec to generate two builds cli, desktop ([ce2b013](https://github.com/tks18/personal-finance-etl/commit/ce2b013d20a8ad2d7e2e829749bd75dbd74fea03))


### Docs 📃

* update documentations ([8fbd1c3](https://github.com/tks18/personal-finance-etl/commit/8fbd1c3d7583c59976a99009f679dc17d5c942e8))
* update readme mermail diag ([693bb20](https://github.com/tks18/personal-finance-etl/commit/693bb203bed59cd67f691ec79f6c5741ecd1bfab))

## [4.3.0](https://github.com/tks18/personal-finance-etl/compare/4.2.0...4.3.0) (2026-08-15)


### Features 🔥

* **engines/analytics:** integrate new metrics ([95fa55c](https://github.com/tks18/personal-finance-etl/commit/95fa55c0ba80361329c6f7918992a101cbd2426a))
* **engines/analytics:** integrate new metrics to isin processor ([fbd5973](https://github.com/tks18/personal-finance-etl/commit/fbd59737815a2e0d1bd8a9531e1149984d4d58e0))
* **engines/analytics:** integrate new risk metrics across all aggregations ([9d83427](https://github.com/tks18/personal-finance-etl/commit/9d834277da244db0f302aaf27bf3feddc4f9f477))
* **engines/analytics:** math: introduce new risk metrics for investments ([a406e29](https://github.com/tks18/personal-finance-etl/commit/a406e29eac0777934c6beb0b34446c3a8b0d53b0))


### Bug Fixes 🛠

* **engines/presentations:** monte_carlo: fix non deterministic seeds, various math fixes ([61a6e5c](https://github.com/tks18/personal-finance-etl/commit/61a6e5c2bc3b5e9883c7a7e7bf2a24e5dca45688))


### Code Refactoring 🖌

* **load/schema:** add new risk metrics ddl ([c43fcc8](https://github.com/tks18/personal-finance-etl/commit/c43fcc83879305ea5117d2ed191e30305d42d913))


### Docs 📃

* update docs - readme, fire guide & metrics guide ([24c99af](https://github.com/tks18/personal-finance-etl/commit/24c99af1ca4dcdead787e25a55c5edb32c872a40))

## [4.2.0](https://github.com/tks18/personal-finance-etl/compare/4.1.6...4.2.0) (2026-08-14)


### Styling 🎨

* lint fixes ([cb2bd90](https://github.com/tks18/personal-finance-etl/commit/cb2bd9003a7d3ad63a5daf6bdf19d7f5934c15a4))


### Features 🔥

* **engines/presentations:** intrroduce new risk metrics to integrrate in wealth risk ([b95cc64](https://github.com/tks18/personal-finance-etl/commit/b95cc64c7202a571444116de9cf9f9c84df5b698))
* **transform:** add dividend tax rate to macro table ([5500411](https://github.com/tks18/personal-finance-etl/commit/5500411e96248ed357487089a1bc6061b597c9c1))


### Bug Fixes 🛠

* **engines/analytics:** fix ltcl offset logic ([af30dc6](https://github.com/tks18/personal-finance-etl/commit/af30dc62d312fee59fd42c3ed9a645c9707af890))
* **engines/presentations:** fix tax liabilities to calculate proper offset logic ([6f8c4ab](https://github.com/tks18/personal-finance-etl/commit/6f8c4abffb56a24840e2d0147bcb958e9da9e302))
* **engines/presentations:** monte_carlo: massive improvement in cpu usage + math fixes ([a638196](https://github.com/tks18/personal-finance-etl/commit/a63819648e4043fd9212254743b58a4331bb3fbb))
* **engines/presentations:** wealth_risk: fix month seeds for mc, add new risk metrics, some refactor ([82816d1](https://github.com/tks18/personal-finance-etl/commit/82816d1760bb72a3eb233de4d5a9c3c6e8f38360))


### Code Refactoring 🖌

* **config/rules:** move more hardcoded params to rules ([88c7c2e](https://github.com/tks18/personal-finance-etl/commit/88c7c2eb5f54b519917d427796f7e1ed3b46e1b9))
* **load:** add new schema ddl for new metrics ([26e6da5](https://github.com/tks18/personal-finance-etl/commit/26e6da5f9d791763fa77929f92a71f2dce6d379a))

### [4.1.6](https://github.com/tks18/personal-finance-etl/compare/4.1.5...4.1.6) (2026-08-12)


### Bug Fixes 🛠

* **engines/presentations:** fix some boolean cols not populating ([efa7948](https://github.com/tks18/personal-finance-etl/commit/efa7948290cc3be6fe045df5bfaf30b3c52a74bd))

### [4.1.5](https://github.com/tks18/personal-finance-etl/compare/4.1.4...4.1.5) (2026-08-12)


### Bug Fixes 🛠

* **engines/presentations:** fix edge cases in monte carlo ([20733ea](https://github.com/tks18/personal-finance-etl/commit/20733eaeaed7985349d20abe219be0cc932b6fcc))
* update ddl ([ab15901](https://github.com/tks18/personal-finance-etl/commit/ab159010c2b3b9512f7651bd9e94decb70949fc3))

### [4.1.4](https://github.com/tks18/personal-finance-etl/compare/4.1.3...4.1.4) (2026-08-11)


### Build System 🏗

* **main.spec:** remove some exclusions ([91ab0b3](https://github.com/tks18/personal-finance-etl/commit/91ab0b3d9793e31d3c6497f27022b54174be4eb1))

### [4.1.3](https://github.com/tks18/personal-finance-etl/compare/4.1.2...4.1.3) (2026-08-11)


### Build System 🏗

* **main.spec:** add few more exclusions to save space ([2931a06](https://github.com/tks18/personal-finance-etl/commit/2931a06d5fe158bcc5fe72791216b70e55e1586a))


### CI 🛠

* **.versionrc.js:** add custom version tracker for version_info.txt file ([b7e6ec7](https://github.com/tks18/personal-finance-etl/commit/b7e6ec7658677beef0f88eed0ec78f60952bc7dd))

### [4.1.2](https://github.com/tks18/personal-finance-etl/compare/4.1.1...4.1.2) (2026-08-11)

### [4.1.1](https://github.com/tks18/personal-finance-etl/compare/4.1.0...4.1.1) (2026-08-11)


### Code Refactoring 🖌

* add full typing to the entire pipeline ([197e14d](https://github.com/tks18/personal-finance-etl/commit/197e14de9c6994a191c907ae2ce99ca46cbf6978))

## [4.1.0](https://github.com/tks18/personal-finance-etl/compare/4.0.0...4.1.0) (2026-08-11)


### Bug Fixes 🛠

* **engines/benchmark:** fix edge cases where cache & api fails to fetch data ([41ed7a7](https://github.com/tks18/personal-finance-etl/commit/41ed7a7847ba25b2efb327fa76a8d928a3fcc231))
* **engines/presentations:** use 12m avgs for better smoothing, constant seed for deterministic outs ([9014984](https://github.com/tks18/personal-finance-etl/commit/9014984e570f874aae64e8cf7670f86152d6139c))
* **engines/presentations:** use 12m avgs for monte carlo ([5a91df4](https://github.com/tks18/personal-finance-etl/commit/5a91df420b819cfce439d59177b4654b06488078))


### Code Refactoring 🖌

* **load/schema:** just add new 12m avgs to wealth analytics ([8af1372](https://github.com/tks18/personal-finance-etl/commit/8af13727cde91eefa4d7cc1e15b67739b7371f2c))

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
