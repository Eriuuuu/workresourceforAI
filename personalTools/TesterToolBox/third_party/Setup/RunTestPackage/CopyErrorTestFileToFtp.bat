rem 批处理所在文件夹
set BatDir=%~dp0
rem 上传文件路径
set HtmlDir=%2
rem 文件名
set FileName=%3

rem 拷贝文件
del /s /q %BatDir%\SaveTestFileToServerFtpCmds.txt
copy %BatDir%\SaveTestFileToServerFtpCmdsTemplate.txt %BatDir%\SaveTestFileToServerFtpCmds.txt
copy %HtmlDir%\TotalResult.html %BatDir%\%FileName%
rem 上传文件
echo put "%BatDir%%FileName%">>%BatDir%\SaveTestFileToServerFtpCmds.txt
echo bye>>%BatDir%\SaveTestFileToServerFtpCmds.txt

ftp -s:%BatDir%\SaveTestFileToServerFtpCmds.txt
rem 删除文件
del /s /q %BatDir%\SaveTestFileToServerFtpCmds.txt
del %BatDir%\%FileName%