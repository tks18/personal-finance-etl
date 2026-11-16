/**
 * Windows PE Resource (version_info.txt) updater for standard-version.
 *
 * Ensures filevers and prodvers are strictly 4-tuples of integers for PyInstaller
 * while keeping StringStruct FileVersion and ProductVersion human-readable.
 *
 * Examples:
 *   9.9.6          -> filevers=(9, 9, 6, 0), FileVersion='9.9.6'
 *   10.0.0-rc.1    -> filevers=(10, 0, 0, 1), FileVersion='10.0.0-rc.1'
 *   10.0.0-rc.10   -> filevers=(10, 0, 0, 10), FileVersion='10.0.0-rc.10'
 *   10.0.0         -> filevers=(10, 0, 0, 0), FileVersion='10.0.0'
 */

function parseVersionTuple(version) {
  const match = version.match(/^(\d+)\.(\d+)\.(\d+)(?:[.-]?(?:rc|alpha|beta|a|b|c|dev|preview|pre)[.-]?(\d+))?/i);
  if (!match) {
    return '0, 0, 0, 0';
  }
  const major = parseInt(match[1], 10);
  const minor = parseInt(match[2], 10);
  const patch = parseInt(match[3], 10);
  const build = match[4] ? parseInt(match[4], 10) : 0;
  return `${major}, ${minor}, ${patch}, ${build}`;
}

module.exports = {
  readVersion: function (contents) {
    const match = contents.match(/StringStruct\('FileVersion', '([^']+)'\)/);
    if (!match) return null;
    return match[1];
  },
  writeVersion: function (contents, version) {
    const tupleStr = parseVersionTuple(version);

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
  parseVersionTuple,
};
