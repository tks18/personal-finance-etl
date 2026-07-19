# Changelog

All notable changes to this project will be documented in this file. See [standard-version](https://github.com/conventional-changelog/standard-version) for commit guidelines.

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
