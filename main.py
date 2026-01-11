import os
import time
import logging
import undetected_chromedriver as uc
from twocaptcha import TwoCaptcha
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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
        self.wait = WebDriverWait(self.driver, 20)

    def _setup_driver(self):
        options = uc.ChromeOptions()
        if os.getenv("GITHUB_ACTIONS") == "true":
            logger.info("检测到 GitHub 环境，启动 Headless 模式")
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
        
        options.add_argument('--window-size=1920,1080') # 强制大分辨率，防止元素重叠
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        return uc.Chrome(options=options)

    def solve_turnstile_with_retry(self, sitekey, retries=3):
        for i in range(retries):
            try:
                logger.info(f"第 {i+1} 次尝试请求 2Captcha 解析...")
                result = self.solver.turnstile(sitekey=sitekey, url=self.driver.current_url)
                if result and 'code' in result:
                    return result['code']
            except Exception as e:
                logger.warning(f"第 {i+1} 次尝试失败: {e}")
                time.sleep(5)
        raise Exception("无法破解验证码")

    def login(self):
        try:
            # 1. 直接访问登录页面 (跳过首页点击，减少出错概率)
            login_url = "https://justrunmy.app/login"
            logger.info(f"直接访问登录页: {login_url}")
            self.driver.get(login_url)

            # 2. 核心：处理可能存在的 iframe
            # 有些登录框被包裹在 iframe 里，Selenium 必须切换进去才能操作
            time.sleep(5) # 给页面一点渲染时间
            if len(self.driver.find_elements(By.TAG_NAME, "iframe")) > 0:
                logger.info("检测到 iframe，尝试切换上下文...")
                try:
                    # 尝试切换到第一个 iframe（通常是登录表单所在的那个）
                    self.driver.switch_to.frame(0) 
                    logger.info("已切换到 iframe")
                except:
                    logger.info("切换 iframe 失败，保持原样")

            # 3. 输入账号和密码
            logger.info("准备输入凭据...")
            # 增加重试逻辑，防止元素虽然在 DOM 里但不可交互
            email_field = self.wait.until(EC.element_to_be_clickable((By.NAME, "email")))
            email_field.clear()
            email_field.send_keys(self.email)
            logger.info("Email 已输入")

            password_field = self.driver.find_element(By.NAME, "password")
            password_field.clear()
            password_field.send_keys(self.password)
            logger.info("密码 已输入")

            # 4. 提取 Sitekey (如果验证码在 iframe 外，可能需要跳回主页面，但通常在内)
            logger.info("正在提取 Sitekey...")
            cf_container = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "cf-turnstile")))
            sitekey = cf_container.get_attribute("data-sitekey")
            logger.info(f"获取到 Sitekey: {sitekey}")

            # 5. 破解验证码
            token = self.solve_turnstile_with_retry(sitekey)

            # 6. 注入 Token
            logger.info("正在注入 Token...")
            self.driver.execute_script(f'document.getElementsByName("cf-turnstile-response")[0].value="{token}";')
            time.sleep(2)

            # 7. 提交登录 (使用 JS 强力点击)
            logger.info("尝试点击提交按钮...")
            submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            self.driver.execute_script("arguments[0].click();", submit_btn)

            # 8. 验证
            logger.info("等待跳转...")
            # 如果在 iframe 里，跳转后可能需要回到主页面才能检测 URL
            self.driver.switch_to.default_content() 
            self.wait.until(EC.url_contains("/panel"))
            logger.info("🎉 登录成功！")

        except Exception as e:
            self.driver.save_screenshot("error_debug.png")
            logger.error(f"❌ 运行失败: {e}")
        finally:
            self.driver.quit()

if __name__ == "__main__":
    bot = JustRunMyAppBot()
    bot.login()
