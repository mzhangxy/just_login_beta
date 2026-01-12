import os
import time
import json
import base64
import logging
import requests
import undetected_chromedriver as uc
from twocaptcha import TwoCaptcha
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from nacl import encoding, public  # 用于加密 GitHub Secret

# 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JustRunMyAppBot:
    def __init__(self):
        # 基础凭据
        self.email = os.getenv("USER_EMAIL")
        self.password = os.getenv("USER_PASSWORD")
        self.api_key = os.getenv("TWOCAPTCHA_API_KEY")
        
        # GitHub Secret 更新相关
        self.gh_token = os.getenv("GH_TOKEN")
        self.gh_repo = os.getenv("GITHUB_REPOSITORY")
        self.cookie_env = os.getenv("USER_COOKIES")
        
        self.app_id = "2126" # 您的应用 ID
        self.solver = TwoCaptcha(self.api_key)
        self.driver = self._init_driver()
        self.wait = WebDriverWait(self.driver, 45)

    def _init_driver(self):
        options = uc.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1920,1080')
        if os.getenv("GITHUB_ACTIONS") == "true":
            logger.info("检测到 GitHub Actions 环境，启用 Headless 模式")
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
        
        driver = uc.Chrome(options=options)
        # 隐藏 webdriver 特征
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        })
        return driver

    def update_github_secret(self, new_json_value):
        """同步更新 GitHub Secret 逻辑"""
        secret_name = "USER_COOKIES"
        if not self.gh_token or not self.gh_repo:
            logger.warning("⚠️ 环境变量 GH_TOKEN 或 GITHUB_REPOSITORY 缺失，跳过 Secret 更新")
            return False

        headers = {
            "Authorization": f"token {self.gh_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        try:
            # 1. 获取仓库公钥
            pub_key_url = f"https://api.github.com/repos/{self.gh_repo}/actions/secrets/public-key"
            response = requests.get(pub_key_url, headers=headers)
            response.raise_for_status()
            key_data = response.json()
            public_key = key_data['key']
            key_id = key_data['key_id']

            # 2. 使用 PyNaCl 加密内容 (SealedBox 模式)
            pk = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
            sealed_box = public.SealedBox(pk)
            encrypted_value = base64.b64encode(
                sealed_box.encrypt(new_json_value.encode("utf-8"))
            ).decode("utf-8")

            # 3. 推送加密后的 Secret 到 GitHub
            put_url = f"https://api.github.com/repos/{self.gh_repo}/actions/secrets/{secret_name}"
            data = {"encrypted_value": encrypted_value, "key_id": key_id}
            res = requests.put(put_url, headers=headers, json=data)
            
            if res.status_code in [201, 204]:
                logger.info(f"✅ GitHub Secret '{secret_name}' 已更新同步")
                return True
            else:
                logger.error(f"❌ Secret 更新失败，响应: {res.text}")
                return False
        except Exception as e:
            logger.error(f"⚠️ 更新 Secret 过程出错: {e}")
            return False

    def load_cookies(self):
        """植入 Cookie 并检查登录态"""
        if not self.cookie_env or len(self.cookie_env) < 50:
            logger.info("ℹ️ Cookie 变量为空或过短，准备进行初次登录")
            return False
        
        try:
            # 必须先打开域名才能注入该域名的 Cookie
            self.driver.get("https://justrunmy.app")
            cookies = json.loads(self.cookie_env)
            for c in cookies:
                # 规范化 SameSite 属性以适配 Selenium
                if "sameSite" in c and c["sameSite"] not in ["Strict", "Lax", "None"]:
                    c["sameSite"] = "Lax"
                self.driver.add_cookie(c)
            
            logger.info("🍪 Cookie 已注入，正在刷新验证...")
            self.driver.refresh()
            time.sleep(5)
            
            if "/panel" in self.driver.current_url:
                logger.info("🎉 Cookie 有效，登录成功！")
                return True
            logger.warning("⚠️ Cookie 已失效")
            return False
        except Exception as e:
            logger.error(f"⚠️ Cookie 注入失败: {e}")
            return False

    def run(self):
        try:
            # 优先尝试 Cookie
            if not self.load_cookies():
                logger.info("Step 1: 启动传统登录流程 (User/Pass + Turnstile)")
                self.driver.get("https://justrunmy.app/account/login")
                time.sleep(3)
                
                # 填写账号密码
                email_input = self.wait.until(EC.visibility_of_element_located((By.NAME, "Email")))
                self.driver.execute_script("arguments[0].value = arguments[1];", email_input, self.email)
                
                pass_input = self.wait.until(EC.visibility_of_element_located((By.NAME, "Password")))
                self.driver.execute_script("arguments[0].value = arguments[1];", pass_input, self.password)

                # 处理验证码
                logger.info("正在获取 Turnstile Sitekey...")
                cf_div = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "cf-turnstile")))
                sitekey = cf_div.get_attribute("data-sitekey")
                
                result = self.solver.turnstile(sitekey=sitekey, url=self.driver.current_url)
                logger.info("验证码破解成功，注入 Token")
                self.driver.execute_script(f'document.querySelector("input[name=\'cf-turnstile-response\']").value = "{result["code"]}";')
                
                # 点击提交
                submit_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]')))
                self.driver.execute_script("arguments[0].click();", submit_btn)
                
                # 验证跳转并保存新 Cookie
                self.wait.until(EC.url_contains("/panel"))
                logger.info("登录成功，正在同步新会话 Cookie...")
                self.update_github_secret(json.dumps(self.driver.get_cookies()))

            # Step 2: 访问具体应用并续期
            target_url = f"https://justrunmy.app/panel/application/{self.app_id}/"
            logger.info(f"Step 2: 访问目标应用页 {target_url}")
            self.driver.get(target_url)
            time.sleep(8)
            self.driver.save_screenshot("debug_app_page.png")

            # 点击重置计时器按钮
            reset_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, '//button[contains(., "Reset Timer")]')))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reset_btn)
            time.sleep(1)
            self.driver.execute_script("arguments[0].click();", reset_btn)
            logger.info("🚀 Reset Timer 已点击，续期任务完成！")
            time.sleep(3)
            self.driver.save_screenshot("debug_final.png")

        except Exception as e:
            self.driver.save_screenshot("error_state.png")
            logger.error(f"❌ 运行中出现错误: {e}")
            raise
        finally:
            self.driver.quit()

if __name__ == "__main__":
    bot = JustRunMyAppBot()
    bot.run()
