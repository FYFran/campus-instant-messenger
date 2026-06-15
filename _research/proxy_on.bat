@echo off
echo ==================================
echo TokenLine - 香港代理
echo ==================================
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 1 /f
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyServer /t REG_SZ /d "47.82.103.247:8888" /f
echo 代理已开启
echo.
echo 打开浏览器访问:
echo https://console.messagecentral.com
echo.
echo 登录: 3170474192@qq.com
echo 密码: @Yf773711
echo.
echo 登录后找 API Keys 或 Settings 拿 Key
echo 拿到后按任意键关代理
start https://console.messagecentral.com
pause
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f
echo 代理已关闭
