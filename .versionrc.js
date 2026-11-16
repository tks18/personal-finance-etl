module.exports = {
  'tag-prefix': '',
  scripts: {
    precommit: 'uv sync && git add uv.lock',
  },
  types: [
    {
      type: 'chore',
      section: 'Others 🔧',
      hidden: false,
    },
    {
      type: 'revert',
      section: 'Reverts ◀',
      hidden: false,
    },
    {
      type: 'feat',
      section: 'Features 🔥',
      hidden: false,
    },
    {
      type: 'fix',
      section: 'Bug Fixes 🛠',
      hidden: false,
    },
    {
      type: 'improvement',
      section: 'Feature Improvements 🛠',
      hidden: false,
    },
    {
      type: 'docs',
      section: 'Docs 📃',
      hidden: false,
    },
    {
      type: 'style',
      section: 'Styling 🎨',
      hidden: false,
    },
    {
      type: 'refactor',
      section: 'Code Refactoring 🖌',
      hidden: false,
    },
    {
      type: 'perf',
      section: 'Performance Improvements 🏎',
      hidden: false,
    },
    {
      type: 'test',
      section: 'Tests 🧪',
      hidden: false,
    },
    {
      type: 'build',
      section: 'Build System 🏗',
      hidden: false,
    },
    {
      type: 'ci',
      section: 'CI 🛠',
      hidden: false,
    },
  ],
  packageFiles: [
    {
      filename: 'package.json',
      type: 'json',
    },
  ],
  bumpFiles: [
    {
      filename: 'package.json',
      type: 'json',
    },
    {
      filename: 'pyproject.toml',
      updater: './scripts/updaters/python.js',
    },
    {
      filename: 'src/personal_finance_etl/__init__.py',
      updater: './scripts/updaters/python.js',
    },
    {
      filename: 'version_info.txt',
      updater: './scripts/updaters/version_info.js',
    },
  ],
};
