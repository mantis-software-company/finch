@echo off
REM Upgrade pip
python -m pip install --upgrade pip

REM Install cx_Freeze
pip install cx_freeze

REM Install the finch package and dependencies
pip install .

REM Clone the botocore repository using the specified version in project.
for /f "delims=" %%i in ('python -c "import botocore; print(botocore.__version__)"') do set botocore_version=%%i
git clone https://github.com/boto/botocore.git vendor\botocore
cd vendor\botocore
git checkout %botocore_version%
cd..\..

REM Trim the botocore data to include only S3.
set "root_dir=vendor\botocore\botocore\data"
for /d %%i in ("%root_dir%\*") do (
    call :delete_non_s3_data "%%i" "%%~nxi"
)

REM Install the trimmed down botocore package
pip install vendor\botocore

goto :eof

:delete_non_s3_data
set "dir=%~1"
set "fname=%~2"
if not "%fname:~0,2%" == "s3" (
    if /i not "%dir%" == "%root_dir%" (
        echo "Directory deleted: %dir%"
        rmdir /s /q "%dir%"
    )
)
goto :eof