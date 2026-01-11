import os
import time
import logging
import undetected_chromedriver as uc
from twocaptcha import TwoCaptcha
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JustRunMyAppBot:
    def __init__(self):
        # 从 GitHub Secrets 读取变量
        self.email = os.getenv("USER_EMAIL")
        self.password = os.getenv("USER_PASSWORD")
        self.api_key = os.getenv("TWOCAPTCHA_API_KEY")
        
        # 初始化 2Captcha 
        self.solver = TwoCaptcha(self.api_key)
        self.driver = self._setup_driver()
        self.wait = WebDriverWait(self.driver, 30)

    def _setup_driver(self):
        options = uc.ChromeOptions()
        # 自动识别环境：GitHub Actions 必须开启无头模式
        if os.getenv("GITHUB_ACTIONS") == "true":
            logger.info("检测到 GitHub 环境，启动 Headless 模式")
            options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
        
        # 伪装 User-Agent
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        return uc.Chrome(options=options)

    def solve_turnstile_with_retry(self, sitekey, retries=3):
        """带有重试机制的验证码破解"""
        for i in range(retries):
            try:
                logger.info(f"第 {i+1} 次尝试请求 2Captcha 解析...")
                result = self.solver.turnstile(
                    sitekey=sitekey,
                    url=self.driver.current_url
                )
                if result and 'code' in result:
                    return result['code']
            except Exception as e:
                logger.warning(f"第 {i+1} 次尝试失败: {e}")
                if i < retries - 1:
                    time.sleep(5)
                else:
                    raise e

    def login(self):
        try:
            # 1. 打开首页
            logger.info("正在打开首页...")
            self.driver.get("https://justrunmy.app")

            # 2. 处理 Cookie 弹窗
            try:
                accept_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Accept All')]")))
                accept_btn.click()
                logger.info("Cookie 弹窗处理完毕")
            except:
                logger.info("未发现 Cookie 弹窗，跳过")

            # 3. 进入登录页
            logger.info("点击 Sign in 按钮...")
            signin_nav = self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign in")))
            signin_nav.click()

            # 4. 输入账号和密码 (放在注入 Token 之前，更符合真人逻辑)
            logger.info("正在输入 Email 和 Password...")
            email_input = self.wait.until(EC.visibility_of_element_located((By.NAME, "email")))
            email_input.send_keys(self.email)
            
            password_input = self.driver.find_element(By.NAME, "password")
            password_input.send_keys(self.password)

            # 5. 等待 CF 盾加载并提取 Sitekey
            logger.info("等待 Cloudflare 盾牌加载...")
            time.sleep(8) # 强制等待，确保 Sitekey 渲染
            cf_container = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "cf-turnstile")))
            sitekey = cf_container.get_attribute("data-sitekey")

            # 6. 获取 2Captcha Token
            token = self.solve_turnstile_with_retry(sitekey)

            # 7. 注入 Token 并登录
            logger.info("正在注入 Token 并执行登录...")
            # 注入 Token 到隐藏框
            self.driver.execute_script(f'document.getElementsByName("cf-turnstile-response")[0].value="{token}";')
            
            # 注入后稍等 2 秒，让网页 JS 捕获到数据变化
            time.sleep(2)

            # 使用 JavaScript 强制点击登录按钮（防止按钮被遮挡导致点击失败）
            submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            self.driver.execute_script("arguments[0].click();", submit_btn)

            # 8. 验证是否跳转成功
            logger.info("正在等待跳转至控制台...")
            self.wait.until(EC.url_contains("/panel"))
            logger.info("🎉 登录成功！当前页面: " + self.driver.title)

        except Exception as e:
            # 截图是云端调试的唯一“眼睛”
            self.driver.save_screenshot("error_debug.png")
            logger.error(f"❌ 运行失败: {e}")
        finally:
            logger.info("流程结束，关闭浏览器")
            self.driver.quit()

if __name__ == "__main__":
    bot = JustRunMyAppBot()
    bot.login()
