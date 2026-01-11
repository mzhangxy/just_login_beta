import os
import time
import logging
import undetected_chromedriver as uc
from twocaptcha import TwoCaptcha
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 日志配置
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JustRunMyAppLoginBot:
    def __init__(self):
        self.email = os.getenv("USER_EMAIL")
        self.password = os.getenv("USER_PASSWORD")
        self.api_key = os.getenv("TWOCAPTCHA_API_KEY")
        
        if not all([self.email, self.password, self.api_key]):
            raise ValueError("缺少环境变量: USER_EMAIL / USER_PASSWORD / TWOCAPTCHA_API_KEY")
        
        self.solver = TwoCaptcha(self.api_key)
        self.driver = self._init_driver()
        self.wait = WebDriverWait(self.driver, 45)

    def _init_driver(self):
        options = uc.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1920,1080')
        
        if os.getenv("GITHUB_ACTIONS") == "true":
            logger.info("运行在 GitHub Actions，使用 headless=new")
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
        
        driver = uc.Chrome(options=options, version_main=130)  # 调整版本如果启动失败
        
        # 隐藏 webdriver 痕迹
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        })
        
        return driver

    def login(self):
        try:
            # 1. 访问首页并处理 cookies 弹窗
            logger.info("Step 1: 打开首页，处理 Cookies 弹窗")
            self.driver.get("https://justrunmy.app")
            time.sleep(3)
            self.driver.save_screenshot("debug_1_home.png")
            
            # 点击 "Accept All"（根据你首页截图的绿按钮）
            try:
                accept_btn = self.wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button:contains("Accept All"), button[id*="accept"], button[class*="accept"]')
                ))
                accept_btn.click()
                logger.info("Cookies 已接受")
                time.sleep(2)
            except:
                logger.warning("未找到 Cookies 接受按钮，跳过")

            # 2. 点击 Sign in
            logger.info("Step 2: 点击 Sign in")
            signin_link = self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign in")))
            signin_link.click()
            time.sleep(4)
            self.driver.save_screenshot("debug_2_signin_clicked.png")

            # 3. 等待到达登录页面（处理重定向）
            logger.info("Step 3: 等待登录页加载")
            self.wait.until(EC.url_contains("/account/login"))
            logger.info(f"当前 URL: {self.driver.current_url}")
            time.sleep(6)  # 给 CF + JS 充分加载时间
            self.driver.save_screenshot("debug_3_login_page.png")

            # 4. 定位并填写邮箱（name="Email"）
            logger.info("Step 4: 填写邮箱")
            email_field = self.wait.until(EC.visibility_of_element_located((By.NAME, "Email")))
            self.driver.execute_script("arguments[0].value = arguments[1];", email_field, self.email)
            logger.info("邮箱已填写")

            # 5. 填写密码（name="Password"）
            password_field = self.wait.until(EC.visibility_of_element_located((By.NAME, "Password")))
            self.driver.execute_script("arguments[0].value = arguments[1];", password_field, self.password)
            logger.info("密码已填写")

            # 6. 处理 Cloudflare Turnstile
            logger.info("Step 6: 处理 CF Turnstile")
            cf_div = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "cf-turnstile")))
            sitekey = cf_div.get_attribute("data-sitekey")
            
            if sitekey:
                logger.info(f"获取 sitekey: {sitekey}")
                result = self.solver.turnstile(sitekey=sitekey, url=self.driver.current_url)
                token = result['code']
                
                # 注入 token（标准方式）
                self.driver.execute_script(
                    f'document.querySelector("input[name=\'cf-turnstile-response\']").value = "{token}";'
                )
                logger.info("Turnstile token 已注入")
                time.sleep(2)  # 等待验证
            else:
                logger.warning("未找到 Turnstile sitekey，跳过验证码")

            # 7. 点击提交按钮
            logger.info("Step 7: 提交登录")
            submit_btn = self.wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'button[type="submit"].btn-primary')
            ))
            self.driver.execute_script("arguments[0].click();", submit_btn)
            time.sleep(5)
            self.driver.save_screenshot("debug_4_submitted.png")

            # 8. 验证是否成功
            self.wait.until(EC.url_contains("/panel"))
            logger.info("登录成功！最终 URL: " + self.driver.current_url)
            self.driver.save_screenshot("success.png")

        except Exception as e:
            self.driver.save_screenshot("error_final.png")
            logger.error(f"登录失败: {str(e)}")
            logger.info(f"失败时 URL: {self.driver.current_url}")
            raise
        finally:
            self.driver.quit()

if __name__ == "__main__":
    bot = JustRunMyAppLoginBot()
    bot.login()
