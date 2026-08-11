const tracker = {
  readVersion: function (contents) {
    const match = contents.match(/(?:version|__version__) = "([^"]+)"/);
    if (!match) return null;
    // Convert Python 5.0.0b3 to SemVer 5.0.0-b3 so the tool can "see" it
    return match[1].replace(/(\d+)([ab]|rc)(\d+)/, '$1-$2$3');
  },
  writeVersion: function (contents, version) {
    // Strip the hyphen for Python: 5.0.0-b3 -> 5.0.0b3
    const pythonVersion = version.replace(/-([ab]|rc)/, '$1');
    return contents.replace(
      /(version|__version__) = "[^"]+"/,
      (m, p1) => `${p1} = "${pythonVersion}"`,
    );
  },
};

const versionInfoTracker = {
  readVersion: function (contents) {
    const match = contents.match(/StringStruct\('FileVersion', '([^']+)'\)/);
    if (!match) return null;
    return match[1];
  },
  writeVersion: function (contents, version) {
    // Convert SemVer '4.1.1' to '4, 1, 1, 0' for Windows fixed info
    const tupleParts = version.split('.').concat(['0', '0', '0', '0']).slice(0, 4);
    const tupleStr = tupleParts.join(', ');
    
    let newContents = contents.replace(
      /filevers=\(\d+, \d+, \d+, \d+\)/g,
      `filevers=(${tupleStr})`
    );
    newContents = newContents.replace(
      /prodvers=\(\d+, \d+, \d+, \d+\)/g,
      `prodvers=(${tupleStr})`
    );
    newContents = newContents.replace(
      /StringStruct\('FileVersion', '[^']+'\)/g,
      `StringStruct('FileVersion', '${version}')`
    );
    newContents = newContents.replace(
      /StringStruct\('ProductVersion', '[^']+'\)/g,
      `StringStruct('ProductVersion', '${version}')`
    );
    return newContents;
  },
};

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
  bumpFiles: [
    {
      filename: 'package.json',
      type: 'json',
    },
    {
      filename: 'pyproject.toml',
      updater: tracker,
    },
    {
      filename: 'src/__init__.py',
      updater: tracker,
    },
    {
      filename: 'version_info.txt',
      updater: versionInfoTracker,
    },
  ],
};
