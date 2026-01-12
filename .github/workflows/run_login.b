name: Auto Login Bot

on:
  workflow_dispatch:
  schedule:
    - cron: '0 0 */2 * *' # 每 2 天运行一次

jobs:
  build:
    runs-on: ubuntu-latest
    # 显式声明权限，确保可以读取代码
    permissions:
      contents: read

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python 3.11
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install --upgrade setuptools
        # ⚠️ 增加了 requests 和 pynacl 用于 Secret 自动更新功能
        pip install --upgrade undetected-chromedriver selenium 2captcha-python fake-useragent requests pynacl

    - name: Setup Chrome for Testing
      uses: browser-actions/setup-chrome@v1
      with:
        chrome-version: stable

    - name: Run Python Script
      env:
        # 1. 基础登录信息
        USER_EMAIL: ${{ secrets.USER_EMAIL }}
        USER_PASSWORD: ${{ secrets.USER_PASSWORD }}
        TWOCAPTCHA_API_KEY: ${{ secrets.TWOCAPTCHA_API_KEY }}
        
        # 2. Cookie 同步核心变量
        # 注意：这里的名字必须和你在脚本中 os.getenv() 的名字一致
        GH_TOKEN: ${{ secrets.GH_TOKEN }}
        USER_COOKIES: ${{ secrets.USER_COOKIES }}
        
        # 3. 环境标识
        GITHUB_ACTIONS: "true"
        # GITHUB_REPOSITORY 是 Actions 默认提供的，不需要在 Secrets 里手动设，直接引用即可
        GITHUB_REPOSITORY: ${{ github.repository }}
      run: python main.py

    - name: Upload Debug Files
      if: always()
      uses: actions/upload-artifact@v4
      with:
        name: debug-files
        path: |
          *.png
          *.log
        retention-days: 3
