set BatDir=%~dp0

set ReleasePackagePath=%2

set TestPackagePath=%3

set ClusterTestServer=%4

set NodejsPath=%5

set testCollectionIniPath=%6

set selectedTestCollectionDirs=%7

set testGlobalConfigIniFilePath=%8

set runtestExePath=%9

%NodejsPath%  PackageAndUpload_Release.js %ReleasePackagePath% %TestPackagePath% %ClusterTestServer% %testCollectionIniPath% %selectedTestCollectionDirs% %testGlobalConfigIniFilePath% %runtestExePath%

pause