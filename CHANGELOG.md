# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

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
