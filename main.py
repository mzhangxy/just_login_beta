import os
import time
import logging
import undetected_chromedriver as uc
from twocaptcha import TwoCaptcha
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JustRunMyAppBot:
    def __init__(self):
        self.email = os.getenv("USER_EMAIL")
        self.password = os.getenv("USER_PASSWORD")
        self.api_key = os.getenv("TWOCAPTCHA_API_KEY")
        
        self.solver = TwoCaptcha(self.api_key)
        self.driver = self._setup_driver()
        self.wait = WebDriverWait(self.driver, 35) # 增加等待时间以应对重定向

    def _setup_driver(self):
        options = uc.ChromeOptions()
        if os.getenv("GITHUB_ACTIONS") == "true":
            logger.info("检测到 GitHub 环境，启动 Headless 模式")
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
        
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        return uc.Chrome(options=options)

    def login(self):
        try:
            # 1. 访问首页并处理 Cookie
            logger.info("正在打开首页并处理重定向...")
            self.driver.get("https://justrunmy.app")
            
            # 2. 点击 Sign in 触发复杂的重定向链
            # 这一步会经历：主页 -> /panel -> /id/account/login?...
            signin_btn = self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign in")))
            signin_btn.click()

            # 3. 【关键修复】等待 URL 彻底稳定在认证页面
            logger.info("等待认证页面加载稳定...")
            self.wait.until(EC.url_contains("account/login"))
            # 强制等待几秒，确保单页应用（SPA）的脚本执行完毕
            time.sleep(6) 
            
            # 确保此时 Selenium 聚焦在主文档，防止被之前的 iframe 干扰
            self.driver.switch_to.default_content()

            # 4. 尝试输入用户名和密码 (使用显式可见性等待)
            logger.info(f"当前 URL: {self.driver.current_url}，准备输入凭据...")
            email_input = self.wait.until(EC.visibility_of_element_located((By.NAME, "email")))
            
            # 使用 JS 强力注入，防止 send_keys 失败
            self.driver.execute_script("arguments[0].value = arguments[1];", email_input, self.email)
            password_input = self.driver.find_element(By.NAME, "password")
            self.driver.execute_script("arguments[0].value = arguments[1];", password_input, self.password)
            logger.info("用户名和密码已注入")

            # 5. 处理 Cloudflare Turnstile (这是你之前能做到的步骤)
            logger.info("正在检测并破解验证码...")
            cf_container = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "cf-turnstile")))
            sitekey = cf_container.get_attribute("data-sitekey")
            
            result = self.solver.turnstile(sitekey=sitekey, url=self.driver.current_url)
            token = result['code']
            
            # 6. 注入 Token 并执行登录
            self.driver.execute_script(f'document.getElementsByName("cf-turnstile-response")[0].value="{token}";')
            logger.info("Token 注入完毕，准备提交")
            
            # 7. 提交表单
            submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            self.driver.execute_script("arguments[0].click();", submit_btn)

            # 8. 最终验证
            self.wait.until(EC.url_contains("/panel"))
            logger.info("🎉 登录成功！")

        except Exception as e:
            self.driver.save_screenshot("error_debug.png")
            logger.error(f"❌ 运行失败: {e}")
            logger.info(f"失败时的 URL: {self.driver.current_url}")
        finally:
            self.driver.quit()

if __name__ == "__main__":
    bot = JustRunMyAppBot()
    bot.login()
