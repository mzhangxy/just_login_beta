import os
import time
import logging
import undetected_chromedriver as uc
from twocaptcha import TwoCaptcha
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class JustRunMyAppBot:
    def __init__(self):
        self.email = os.getenv("USER_EMAIL", "你的邮箱")
        self.password = os.getenv("USER_PASSWORD", "你的密码")
        self.api_key = os.getenv("TWOCAPTCHA_API_KEY", "你的API_KEY")

        # 初始化 2Captcha，并设置超时时间长一点，应对网络波动
        self.solver = TwoCaptcha(self.api_key)
        self.driver = self._setup_driver()
        self.wait = WebDriverWait(self.driver, 30)

    def _setup_driver(self):
        options = uc.ChromeOptions()
        if os.getenv("GITHUB_ACTIONS"):
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        return uc.Chrome(options=options)

    def solve_turnstile_with_retry(self, sitekey, retries=3):
        """增加重试机制，应对 SSL 连接中断问题"""
        for i in range(retries):
            try:
                logger.info(f"第 {i + 1} 次尝试请求 2Captcha 解析...")
                # 使用通用的 solve 方法，有时比直接调用 turnstile 更稳
                result = self.solver.solve({
                    'method': 'turnstile',
                    'sitekey': sitekey,
                    'pageurl': self.driver.current_url
                })
                return result['code']
            except Exception as e:
                logger.warning(f"第 {i + 1} 次请求失败: {e}")
                if i < retries - 1:
                    time.sleep(5)  # 等待 5 秒后重试
                else:
                    raise e

    def login(self):
        try:
            logger.info("正在打开首页...")
            self.driver.get("https://justrunmy.app")

            # 1. 处理 Cookie
            try:
                accept_btn = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept All')]")))
                accept_btn.click()
                logger.info("Cookie 弹窗已处理")
            except:
                pass

            # 2. 点击登录
            signin_nav = self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign in")))
            signin_nav.click()

            # --- 关键修改点：等待 CF 盾完全渲染 ---
            logger.info("进入登录页，等待网页完全加载...")
            time.sleep(8)  # 额外给 8 秒，让 Turnstile 那个小方块彻底转出来

            # 确保容器已经出现在 DOM 中
            cf_container = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "cf-turnstile")))
            sitekey = cf_element = cf_container.get_attribute("data-sitekey")

            if not sitekey:
                logger.error("未能提取到 Sitekey，页面可能未完全加载")
                return

            # 3. 破解验证码（带重试机制）
            token = self.solve_turnstile_with_retry(sitekey)

            # 4. 注入 Token
            self.driver.execute_script(f'document.getElementsByName("cf-turnstile-response")[0].value="{token}";')
            # 触发潜在的回调
            self.driver.execute_script('if(window.cfCallback){cfCallback();}')
            logger.info("Token 注入完毕")

            # 5. 输入账号
            self.wait.until(EC.visibility_of_element_located((By.NAME, "email"))).send_keys(self.email)
            self.driver.find_element(By.NAME, "password").send_keys(self.password)

            # 6. 提交
            self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()

            # 7. 验证
            self.wait.until(EC.url_contains("/panel"))
            logger.info("🎉 登录成功！")

        except Exception as e:
            self.driver.save_screenshot("error_debug.png")
            logger.error(f"失败原因: {e}")
        finally:
            self.driver.quit()


if __name__ == "__main__":
    bot = JustRunMyAppBot()
    bot.login()
