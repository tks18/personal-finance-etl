# -*- mode: python ; coding: utf-8 -*-
import PyInstaller.config
from PyInstaller.utils.hooks import copy_metadata, collect_data_files, collect_submodules, collect_dynamic_libs

PyInstaller.config.CONF['upx_dir'] = r"C:\Tools\_bins_\upx"

datas = [('logo.ico', '.'), ('logo.png', '.'), ('README.md', '.'), ('docs/*', 'docs/')]
binaries = []

hiddenimports = [
    'darkdetect',
    'win32timezone',
    'polars',
    'pyxirr',
    'yfinance',
    'customtkinter',
    'numpy',
    'pandas',
    'tomllib',
    'rich',
    'webview',
    'markdown',
    'personal_finance_etl.frontend.cli.app',
    'personal_finance_etl.frontend.app',
    'personal_finance_etl.frontend.base_tab',
    'personal_finance_etl.backend.engines.tax_engine',
    'personal_finance_etl.backend.engines.benchmark_engine',
    'personal_finance_etl.backend.engines.pipeline.context',
    'personal_finance_etl.backend.engines.pipeline.processor',
    'personal_finance_etl.backend.engines.pipeline.postprocessor',
    'personal_finance_etl.backend.load.database',
    'personal_finance_etl.backend.utils.helpers',
    'personal_finance_etl.backend.utils.models',
    'personal_finance_etl.backend.utils.theme',
    'personal_finance_etl.backend.utils.logger',
    'personal_finance_etl.backend.extract.excel_parser',
    'personal_finance_etl.backend.extract.sqlite_extractor',
    'personal_finance_etl.backend.transform.core',
    'personal_finance_etl.backend.transform.stocks',
    'personal_finance_etl.backend.transform.mutual_funds',
    'personal_finance_etl.backend.pipeline.etl_pipeline',
    'personal_finance_etl.backend.config.settings',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'notebook', 'nbconvert', 'nbformat',
        'jedi', 'IPython', 'tkinter.test', 'unittest',
        'PyQt5', 'PySide2', 'PySide6', 'PyQt6',
        'openpyxl', 'xlsxwriter', 'xlrd', 'pyxlsb', 'odf',
        'sqlalchemy', 'boto3', 'botocore', 's3fs', 'gcsfs', 'fsspec',
        'bokeh', 'plotly', 'altair', 'seaborn',
        'pytest', 'pdb', 'idlelib',
        'pydantic.v1', 'pydantic.tests', 'pydantic._internal.tests',
        'numba.tests', 'numpy.random.tests', 'numpy.core.tests', 'pandas.tests', 'pyarrow.tests',
        'pyarrow.flight', 'pyarrow.cuda', 'pyarrow.ganesha',
        'duckdb.tests', 'psutil.tests', 'cryptography',
        'PIL.ImageQt', 'PIL.ImageWebP',
        'mypy', 'mypyc', 'pyright', 'black', 'flake8', 'isort', 'ruff',
        'poethepoet', 'pyinstaller', 'tkreload', 'vulture'
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe_gui = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Shan\'s Personal Finance ETL',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico',
    version='version_info.txt',
)

exe_cli = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Shan\'s Personal Finance ETL CLI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='logo.ico',
    version='version_info.txt',
)
