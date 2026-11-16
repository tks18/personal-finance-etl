/**
 * Python PEP 440 version updater for standard-version.
 *
 * Converts between SemVer 2.0.0 (used by standard-version, package.json, and git tags)
 * and PEP 440 (used by pyproject.toml and src/personal_finance_etl/__init__.py).
 *
 * Examples:
 *   10.0.0-rc.1     <-> 10.0.0rc1
 *   10.0.0-rc.2     <-> 10.0.0rc2
 *   10.0.0-alpha.1  <-> 10.0.0a1
 *   10.0.0-beta.3   <-> 10.0.0b3
 *   10.0.0          <-> 10.0.0
 */

function toSemver(pyVersion) {
  if (!pyVersion) return null;
  const pepMatch = pyVersion.match(/^(\d+\.\d+\.\d+)(?:(rc|a|b|c|dev)(\d+))?$/i);
  if (pepMatch) {
    const base = pepMatch[1];
    const preType = (pepMatch[2] || '').toLowerCase();
    const preNum = pepMatch[3];
    if (!preType) return base;
    let semType = 'rc';
    if (preType === 'a') semType = 'alpha';
    else if (preType === 'b') semType = 'beta';
    else if (preType === 'dev') semType = 'dev';
    return `${base}-${semType}.${preNum}`;
  }
  return pyVersion;
}

function toPythonVersion(semver) {
  if (!semver) return '';
  const match = semver.match(/^(\d+\.\d+\.\d+)(?:-(alpha|beta|rc|preview|pre|dev|a|b|c)\.?(\d+))?$/i);
  if (match) {
    const base = match[1];
    const rawType = (match[2] || '').toLowerCase();
    const preNum = match[3] || '0';
    if (!match[2]) return base;
    let pepType = 'rc';
    if (rawType === 'alpha' || rawType === 'a') pepType = 'a';
    else if (rawType === 'beta' || rawType === 'b') pepType = 'b';
    else if (rawType === 'dev') pepType = 'dev';
    else if (rawType === 'rc' || rawType === 'c' || rawType === 'preview' || rawType === 'pre') pepType = 'rc';
    return `${base}${pepType}${preNum}`;
  }
  return semver.replace(/-([ab]|rc)\.?(\d+)?/i, '$1$2');
}

module.exports = {
  readVersion: function (contents) {
    const match = contents.match(/(?:version|__version__) = "([^"]+)"/);
    if (!match) return null;
    return toSemver(match[1]);
  },
  writeVersion: function (contents, version) {
    const pythonVersion = toPythonVersion(version);
    return contents.replace(
      /(version|__version__) = "[^"]+"/,
      (m, p1) => `${p1} = "${pythonVersion}"`
    );
  },
  toSemver,
  toPythonVersion,
};
