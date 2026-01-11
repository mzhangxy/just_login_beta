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
        
        if not all([self.email, self.password, self.api_key]):
            raise ValueError("缺少必要的环境变量：USER_EMAIL, USER_PASSWORD 或 TWOCAPTCHA_API_KEY")
        
        self.solver = TwoCaptcha(self.api_key)
        self.driver = self._setup_driver()
        self.wait = WebDriverWait(self.driver, 40)

    def _setup_driver(self):
        options = uc.ChromeOptions()
        
        # 有效的反检测参数
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-infobars')
        options.add_argument('--window-size=1920,1080')
        
        if os.getenv("GITHUB_ACTIONS") == "true":
            logger.info("GitHub Actions 环境 - 使用 headless=new 模式")
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
        else:
            logger.info("本地环境 - 非 headless 模式")
        
        # 随机化 User-Agent（如果安装了 fake-useragent 更好）
        try:
            from fake_useragent import UserAgent
            ua = UserAgent()
            random_ua = ua.random
            options.add_argument(f'--user-agent={random_ua}')
            logger.info(f"使用随机 User-Agent: {random_ua}")
        except ImportError:
            options.add_argument(
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
            )
        
        # 创建 driver
        driver = uc.Chrome(
            options=options,
            version_main=130,          # 根据你的 runner 环境调整，失败可改为 None 让自动检测
            headless=bool(os.getenv("GITHUB_ACTIONS"))
        )
        
        # 额外隐藏 webdriver 痕迹（推荐使用 CDP）
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US', 'en'] });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            """
        })
        
        return driver

    def login(self):
        try:
            # Step 1: 首页
            logger.info("Step 1: 打开首页")
            self.driver.get("https://justrunmy.app")
            time.sleep(3)
            self.driver.save_screenshot("debug_1_homepage.png")
            logger.info(f"首页标题: {self.driver.title.strip()}")
            logger.info(f"首页 URL: {self.driver.current_url}")

            # Step 2: 点击 Sign in
            logger.info("Step 2: 寻找并点击 Sign in")
            try:
                signin_btn = self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign in")))
                signin_btn.click()
                logger.info("使用 Link Text 成功点击 Sign in")
            except:
                logger.warning("Link Text 'Sign in' 未找到，尝试其他方式...")
                signin_btn = self.wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'a[href*="login"], a[href*="account"], a:contains("Sign"), button:contains("Sign")')
                ))
                signin_btn.click()

            time.sleep(4)
            self.driver.save_screenshot("debug_2_after_signin_click.png")

            # Step 3: 等待登录页面
            logger.info("Step 3: 等待到达登录页面...")
            self.wait.until(EC.url_contains("account/login"))
            logger.info(f"当前 URL: {self.driver.current_url}")

            time.sleep(6)  # 给 JS/Cloudflare 更多加载时间
            self.driver.save_screenshot("debug_3_login_page.png")

            # 检查 Cloudflare 痕迹
            page_source_lower = self.driver.page_source.lower()
            if any(x in page_source_lower for x in ["checking your browser", "cf-browser-verification", "turnstile"]):
                logger.error("!!! 检测到 Cloudflare 验证页面 !!! 很可能被拦截")

            # 尝试处理 iframe
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            logger.info(f"页面中共找到 {len(iframes)} 个 iframe")
            in_frame = False
            for i, iframe in enumerate(iframes):
                try:
                    src = iframe.get_attribute("src") or "(无 src)"
                    logger.info(f"iframe {i+1}: {src}")
                    self.driver.switch_to.frame(iframe)
                    if self.driver.find_elements(By.TAG_NAME, "input"):
                        logger.info("→ 在此 iframe 内找到表单元素！保持在此 frame")
                        in_frame = True
                        break
                    self.driver.switch_to.default_content()
                except:
                    self.driver.switch_to.default_content()

            # 列出所有 input（关键诊断信息）
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            logger.info(f"当前上下文中共找到 {len(inputs)} 个 <input> 元素")
            for idx, inp in enumerate(inputs):
                try:
                    info = {
                        "name": inp.get_attribute("name") or "(无)",
                        "type": inp.get_attribute("type") or "(无)",
                        "id": inp.get_attribute("id") or "(无)",
                        "placeholder": inp.get_attribute("placeholder") or "(无)",
                        "visible": inp.is_displayed()
                    }
                    logger.info(f"Input {idx+1}: {info}")
                except:
                    pass

            # 尝试定位邮箱输入框（多重 fallback）
            email_selectors = [
                (By.NAME, "Input.Username"),
                (By.NAME, "email"),
                (By.NAME, "username"),
                (By.CSS_SELECTOR, 'input[type="email"], input[placeholder*="mail" i]'),
                (By.XPATH, '//input[contains(@type,"email") or contains(@name,"user") or contains(@placeholder,"mail")]')
            ]

            email_input = None
            for by, value in email_selectors:
                try:
                    email_input = self.wait.until(EC.visibility_of_element_located((by, value)))
                    logger.info(f"成功定位邮箱输入框: {by} = {value}")
                    break
                except:
                    continue

            if not email_input:
                raise Exception("所有邮箱定位方式都失败，请查看上面 input 列表和 debug_3_login_page.png")

            # 输入邮箱 & 密码
            self.driver.execute_script("arguments[0].value = arguments[1];", email_input, self.email)
            logger.info("邮箱已注入")

            password_input = self.wait.until(EC.visibility_of_element_located(
                (By.CSS_SELECTOR, 'input[type="password"]')
            ))
            self.driver.execute_script("arguments[0].value = arguments[1];", password_input, self.password)
            logger.info("密码已注入")

            # 处理 Turnstile
            try:
                cf = self.driver.find_element(By.CSS_SELECTOR, ".cf-turnstile, [data-sitekey]")
                sitekey = cf.get_attribute("data-sitekey")
                if sitekey:
                    logger.info(f"检测到 Turnstile，sitekey: {sitekey}")
                    result = self.solver.turnstile(sitekey=sitekey, url=self.driver.current_url)
                    token = result['code']
                    self.driver.execute_script(
                        f'document.querySelector("[name=\'cf-turnstile-response\']").value = "{token}";'
                    )
                    logger.info("Turnstile token 已注入")
                    time.sleep(2)
            except:
                logger.info("未检测到 Turnstile，跳过验证码步骤")

            # 提交
            submit_btn = self.wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[type='submit'], button:contains('SIGN IN'), button:contains('登录')")
            ))
            self.driver.execute_script("arguments[0].click();", submit_btn)
            logger.info("已点击提交按钮")

            # 等待跳转成功
            self.wait.until(EC.url_contains("/panel"))
            logger.info("登录成功！当前 URL: " + self.driver.current_url)
            self.driver.save_screenshot("debug_success.png")

        except Exception as e:
            self.driver.save_screenshot("error_final.png")
            logger.error(f"执行失败: {str(e)}")
            logger.info(f"失败时 URL: {self.driver.current_url}")
            logger.info(f"失败时标题: {self.driver.title}")
            raise
        finally:
            self.driver.quit()

if __name__ == "__main__":
    bot = JustRunMyAppBot()
    bot.login()
