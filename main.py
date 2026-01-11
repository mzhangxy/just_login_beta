import os
import time
import logging
import undetected_chromedriver as uc
from twocaptcha import TwoCaptcha
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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
        self.wait = WebDriverWait(self.driver, 60)  # 增加超时到60s，应对 SPA 慢加载

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
        
        driver = uc.Chrome(options=options, version_main=143)
        
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        })
        
        return driver

    def login(self):
        try:
            logger.info("Step 1: 打开首页，处理 Cookies")
            self.driver.get("https://justrunmy.app")
            time.sleep(3)
            self.driver.save_screenshot("debug_1_home.png")
            
            try:
                accept_btn = self.wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button:contains("Accept All"), button[id*="accept"], button[class*="accept"]')
                ))
                accept_btn.click()
                logger.info("Cookies 已接受")
                time.sleep(2)
            except:
                logger.warning("未找到 Cookies 按钮，跳过")

            logger.info("Step 2: 点击 Sign in")
            signin_link = self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign in")))
            signin_link.click()
            time.sleep(4)
            self.driver.save_screenshot("debug_2_signin_clicked.png")

            logger.info("Step 3: 等待登录页")
            self.wait.until(EC.url_contains("/account/login"))
            logger.info(f"登录页 URL: {self.driver.current_url}")
            time.sleep(6)
            self.driver.save_screenshot("debug_3_login_page.png")

            logger.info("Step 4: 填写邮箱")
            email_field = self.wait.until(EC.visibility_of_element_located((By.NAME, "Email")))
            self.driver.execute_script("arguments[0].value = arguments[1];", email_field, self.email)
            logger.info("邮箱已填写")

            password_field = self.wait.until(EC.visibility_of_element_located((By.NAME, "Password")))
            self.driver.execute_script("arguments[0].value = arguments[1];", password_field, self.password)
            logger.info("密码已填写")

            logger.info("Step 6: 处理 CF Turnstile")
            cf_div = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "cf-turnstile")))
            sitekey = cf_div.get_attribute("data-sitekey")
            if sitekey:
                logger.info(f"sitekey: {sitekey}")
                result = self.solver.turnstile(sitekey=sitekey, url=self.driver.current_url)
                token = result['code']
                self.driver.execute_script(f'document.querySelector("input[name=\'cf-turnstile-response\']").value = "{token}";')
                logger.info("Token 已注入")
                time.sleep(2)

            logger.info("Step 7: 提交登录")
            submit_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"].btn-primary')))
            self.driver.execute_script("arguments[0].click();", submit_btn)
            time.sleep(5)
            self.driver.save_screenshot("debug_4_submitted.png")

            self.wait.until(EC.url_contains("/panel"))
            logger.info("登录成功！URL: " + self.driver.current_url)
            self.driver.save_screenshot("debug_5_panel.png")

            # Step 9: 点击 hello-world 卡片，并等待 URL 变化到 /panel/application/
            logger.info("Step 9: 点击 hello-world 卡片")
            app_card = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//div[contains(text(), "hello-world") or contains(., "hello-world")]')
            ))
            self.driver.execute_script("arguments[0].click();", app_card)
            time.sleep(3)

            # 关键：等待 URL 变化为 /panel/application/
            self.wait.until(EC.url_contains("/panel/application/"))
            logger.info(f"进入详情页 URL: {self.driver.current_url}")
            time.sleep(5)  # 额外缓冲 SPA 加载
            self.driver.save_screenshot("debug_6_app_detail.png")

            # 等待详情页特定内容加载（从源码看有 "INACTIVITY SHUTDOWN TIMER"）
            self.wait.until(EC.presence_of_element_located(
                (By.XPATH, '//div[contains(text(), "INACTIVITY") or contains(text(), "SHUTDOWN TIMER")]')
            ))
            logger.info("详情页内容已加载")

            # Step 10: 检查 Running
            logger.info("Step 10: 检查 Running 状态")
            is_running = False
            try:
                self.wait.until(EC.presence_of_element_located(
                    (By.XPATH, '//div[contains(text(), "Running") or contains(., "Running")]')
                ))
                is_running = True
                logger.info("检测到 Running，直接重置定时器")
            except:
                logger.info("未检测到 Running，先重启")

            if not is_running:
                logger.info("点击 Restart 按钮")
                restart_btn = self.wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[class*="bg-slate-50"], button:contains("Restart")')
                ))
                self.driver.execute_script("arguments[0].click();", restart_btn)
                time.sleep(5)
                self.driver.save_screenshot("debug_7_after_restart.png")
                
                self.wait.until(EC.presence_of_element_located(
                    (By.XPATH, '//div[contains(text(), "Running") or contains(., "Running")]')
                ))
                logger.info("重启后 Running 出现")

            # Step 11: 点击 Reset Timer（优化 selector）
            logger.info("Step 11: 点击 Reset Timer 按钮")
            # 打印源码调试
            page_source_lower = self.driver.page_source.lower()
            reset_pos = page_source_lower.find('reset')
            if reset_pos != -1:
                logger.info(f"源码中 'reset' 附近片段: {page_source_lower[reset_pos-100:reset_pos+500]}...")
            else:
                logger.info("源码中未找到 'reset' 关键词")

            reset_btn = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//button[contains(@class, "bg-emerald-500") or contains(@class, "emerald")]')
            ))
            logger.info("使用 class 含 'emerald-500' 定位成功")

            self.driver.execute_script("arguments[0].click();", reset_btn)
            time.sleep(4)
            self.driver.save_screenshot("debug_8_after_reset.png")
            logger.info("定时器已重置，续费完成！")

        except Exception as e:
            self.driver.save_screenshot("error_final.png")
            logger.error(f"操作失败: {str(e)}")
            logger.info(f"失败时 URL: {self.driver.current_url}")
            raise
        finally:
            self.driver.quit()

if __name__ == "__main__":
    bot = JustRunMyAppLoginBot()
    bot.login()
