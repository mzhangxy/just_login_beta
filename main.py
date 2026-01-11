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
            logger.info("Step 1: 打开首页")
            self.driver.get("https://justrunmy.app")
            time.sleep(3)  # 给首页一点缓冲
            self.driver.save_screenshot("debug_1_homepage.png")
            logger.info(f"首页标题: {self.driver.title}")
            logger.info(f"首页 URL: {self.driver.current_url}")
            logger.info(f"首页 source 前200字: {self.driver.page_source[:200]}...")

            # Step 2: 找 Sign in 按钮并点击
            logger.info("Step 2: 尝试点击 Sign in")
            try:
                signin_btn = self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign in")))
                signin_btn.click()
                logger.info("成功点击 Sign in (用 Link Text)")
            except:
                logger.warning("没找到 Link Text 'Sign in'，尝试 CSS 选择器...")
                signin_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href*="login"], a[href*="account"], button:contains("Sign in")')))
                signin_btn.click()

            time.sleep(4)
            self.driver.save_screenshot("debug_2_after_click_signin.png")
    
            # Step 3: 等登录页出现
            logger.info("Step 3: 等待 URL 包含 account/login")
            self.wait.until(EC.url_contains("account/login"))
            logger.info(f"到达登录页 URL: {self.driver.current_url}")
    
            # 关键诊断点：打印页面源码 + 找所有 input
            time.sleep(5)  # 额外等 SPA/JS 加载
            self.driver.save_screenshot("debug_3_login_page_before_input.png")
            
            page_source = self.driver.page_source.lower()
            logger.info("页面标题: " + self.driver.title)
            
            # 检查是否卡在 Cloudflare
            if "checking your browser" in page_source or "turnstile" in page_source or "cf-browser-verification" in page_source:
                logger.error("!!! 疑似卡在 Cloudflare 验证页面 !!!")
                logger.info("页面源码片段: " + page_source[page_source.find("cf-"):page_source.find("cf-")+500])
            
            # 列出所有可见的 input 元素（超级有用！）
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            logger.info(f"页面中共找到 {len(inputs)} 个 <input> 元素")
            for i, inp in enumerate(inputs):
                try:
                    name = inp.get_attribute("name") or "(无name)"
                    typ = inp.get_attribute("type") or "(无type)"
                    id_ = inp.get_attribute("id") or "(无id)"
                    ph = inp.get_attribute("placeholder") or "(无placeholder)"
                    visible = inp.is_displayed()
                    logger.info(f"Input {i+1}: name={name}, type={typ}, id={id_}, placeholder={ph}, visible={visible}")
                except:
                    pass

            # 再检查 cf-turnstile
            try:
                cf = self.driver.find_element(By.CLASS_NAME, "cf-turnstile")
                logger.info("找到 cf-turnstile！ sitekey = " + cf.get_attribute("data-sitekey"))
            except:
                logger.warning("没找到 cf-turnstile 容器")

            # 如果到这里还有 input，就尝试用最宽松的方式定位邮箱
            if inputs:
                email_input = None
                for selector in [
                    (By.NAME, "Input.Username"),
                    (By.NAME, "email"),
                    (By.NAME, "username"),
                    (By.CSS_SELECTOR, 'input[type="email"], input[placeholder*="mail" i], input[name*="user" i]'),
                    (By.XPATH, '//input[contains(@type,"email") or contains(@name,"user") or contains(@placeholder,"mail")]')
                ]:
                    try:
                        email_input = self.wait.until(EC.visibility_of_element_located(selector))
                        logger.info(f"成功用 {selector} 找到邮箱输入框！")
                        break
                    except:
                        continue
            
                if email_input:
                    self.driver.execute_script("arguments[0].value = arguments[1];", email_input, self.email)
                    # ... 后面密码同理，找 type=password 的第一个
                    password_input = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[type="password"]')))
                    self.driver.execute_script("arguments[0].value = arguments[1];", password_input, self.password)
                    # 继续你的 turnstile 和提交逻辑...
                else:
                    raise Exception("所有尝试定位邮箱输入框都失败了，看上面 input 列表！")

        # ... 你原来的 turnstile + 提交代码保持不变 ...

        self.wait.until(EC.url_contains("/panel"))
        logger.info("🎉 登录成功！")

    except Exception as e:
        self.driver.save_screenshot("error_debug_final.png")
        logger.error(f"❌ 运行失败: {str(e)}")
        logger.info(f"失败时的 URL: {self.driver.current_url}")
        logger.info(f"失败时页面标题: {self.driver.title}")
    finally:
        self.driver.quit()

if __name__ == "__main__":
    bot = JustRunMyAppBot()
    bot.login()
