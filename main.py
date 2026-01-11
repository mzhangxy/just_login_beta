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
        # 如果你愿意，可以将 ID 也设为环境变量，或直接改下面的代码
        self.app_id = "2126" 
        
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
        
        # version_main 建议根据环境调整，通常 uc 会自动处理
        driver = uc.Chrome(options=options) 
        
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        })
        
        return driver

    def login(self):
        try:
            # 1. 访问首页
            logger.info("Step 1: 打开首页")
            self.driver.get("https://justrunmy.app")
            time.sleep(3)
            
            # 处理 Cookies 弹窗
            try:
                accept_btn = self.wait.until(EC.element_to_be_clickable(
                    (By.XPATH, '//button[contains(., "Accept") or contains(., "Agree")]')
                ))
                accept_btn.click()
                logger.info("Cookies 已接受")
            except:
                logger.warning("未找到 Cookies 按钮，跳过")

            # 2. 点击 Sign in
            logger.info("Step 2: 点击 Sign in")
            signin_link = self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign in")))
            signin_link.click()

            # 3. 等待登录页加载
            logger.info("Step 3: 等待登录页加载")
            self.wait.until(EC.url_contains("/account/login"))
            time.sleep(5) 

            # 4. 填写邮箱
            logger.info("Step 4: 填写邮箱")
            email_field = self.wait.until(EC.visibility_of_element_located((By.NAME, "Email")))
            self.driver.execute_script("arguments[0].value = arguments[1];", email_field, self.email)

            # 5. 填写密码
            password_field = self.wait.until(EC.visibility_of_element_located((By.NAME, "Password")))
            self.driver.execute_script("arguments[0].value = arguments[1];", password_field, self.password)

            # 6. 处理 Cloudflare Turnstile
            logger.info("Step 6: 处理 CF Turnstile")
            try:
                cf_div = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "cf-turnstile")))
                sitekey = cf_div.get_attribute("data-sitekey")
                if sitekey:
                    logger.info(f"获取 sitekey: {sitekey}")
                    result = self.solver.turnstile(sitekey=sitekey, url=self.driver.current_url)
                    token = result['code']
                    self.driver.execute_script(
                        f'document.querySelector("input[name=\'cf-turnstile-response\']").value = "{token}";'
                    )
                    logger.info("Turnstile token 已注入")
                    time.sleep(2)
            except Exception as e:
                logger.warning(f"验证码处理跳过或失败: {e}")

            # 7. 提交登录
            logger.info("Step 7: 提交登录")
            submit_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]')))
            self.driver.execute_script("arguments[0].click();", submit_btn)

            # 8. 验证成功并跳转
            self.wait.until(EC.url_contains("/panel"))
            logger.info("登录成功，进入控制面板")
            self.driver.save_screenshot("debug_5_panel.png")

            # 9. 直接导航至应用详情页 (方案 A：最稳妥)
            logger.info(f"Step 9: 直接导航至应用 {self.app_id} 详情页")
            detail_url = f"https://justrunmy.app/panel/application/{self.app_id}/"
            self.driver.get(detail_url)
            
            # 等待详情页关键元素加载（比如 Reset 按钮或应用名称）
            time.sleep(8) 
            self.driver.save_screenshot("debug_6_app_detail.png")

            # 10. 检查运行状态并重置定时器
            logger.info("Step 10: 检查并操作 Reset Timer")
            
            # 定位 Reset Timer 按钮 (使用包含文本的 XPath，更通用)
            reset_xpath = '//button[contains(., "Reset Timer")]'
            
            try:
                # 滚动到按钮位置，确保在 Headless 下可见
                reset_btn = self.wait.until(EC.presence_of_element_located((By.XPATH, reset_xpath)))
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reset_btn)
                time.sleep(2)
                
                # 点击按钮
                self.driver.execute_script("arguments[0].click();", reset_btn)
                logger.info("成功点击 Reset Timer 按钮")
                
                time.sleep(3)
                self.driver.save_screenshot("debug_7_done.png")
                logger.info("续费流程结束")

            except Exception as e:
                logger.error(f"未找到 Reset 按钮或点击失败: {e}")
                # 如果没找到 Reset，可能是因为应用没运行，尝试寻找 Restart
                logger.info("尝试寻找 Restart 按钮...")
                try:
                    restart_btn = self.driver.find_element(By.XPATH, '//button[contains(., "Restart")]')
                    self.driver.execute_script("arguments[0].click();", restart_btn)
                    logger.info("已点击 Restart 按钮")
                except:
                    logger.error("Restart 按钮也未找到")

        except Exception as e:
            self.driver.save_screenshot("error_final.png")
            logger.error(f"操作失败: {str(e)}")
            raise
        finally:
            self.driver.quit()

if __name__ == "__main__":
    bot = JustRunMyAppLoginBot()
    bot.login()
