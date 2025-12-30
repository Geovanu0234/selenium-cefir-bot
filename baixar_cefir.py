import os
import glob
import time
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

USUARIO, SENHA = range(2)


def get_latest_pdf(download_folder):
    pdf_files = glob.glob(os.path.join(download_folder, "*.pdf"))
    if not pdf_files:
        return None
    return max(pdf_files, key=os.path.getctime)


def rodar_selenium(usuario, senha, download_folder):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    prefs = {"download.default_directory": download_folder}
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    erro = False
    try:
        driver.get("https://sistema.seia.ba.gov.br/")
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "j_username")))

        driver.find_element(By.ID, "j_username").send_keys(usuario)
        driver.find_element(By.ID, "j_password").send_keys(senha)
        driver.find_element(By.ID, "btnEntrar").click()

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Cadastro')]"))
        )

        driver.find_element(By.XPATH, "//a[contains(text(), 'Cadastro')]").click()
        driver.find_element(By.LINK_TEXT, "Imóvel Rural - CEFIR").click()

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "filtroImoveis:j_idt266"))
        )

        driver.find_element(By.ID, "filtroImoveis:j_idt266").click()
        time.sleep(1)

        driver.find_element(By.XPATH, "//li[contains(., 'Monte Santo')]").click()

        WebDriverWait(driver, 60).until(
            EC.invisibility_of_element_located((By.ID, "statusDialog"))
        )

        botao_consultar = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.ID, "filtroImoveis:btnConsulta"))
        )
        botao_consultar.click()

        WebDriverWait(driver, 90).until(
            EC.invisibility_of_element_located((By.ID, "statusDialog"))
        )

        botao_acoes = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "span.ui-row-toggler"))
        )
        botao_acoes.click()

        botao_pdf = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.XPATH, "//img[@title='Visualizar Termo de Compromisso']"))
        )
        botao_pdf.click()

        time.sleep(10)

    except Exception as e:
        print("Erro Selenium:", e)
        erro = True
    finally:
        driver.quit()

    return not erro


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bem-vindo! Envie seu usuário:")
    return USUARIO


async def receber_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["usuario"] = update.message.text
    await update.message.reply_text("Agora envie sua senha:")
    return SENHA


async def receber_senha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = context.user_data["usuario"]
    senha = update.message.text

    await update.message.reply_text("Processando, aguarde...")

    download_folder = "/tmp/downloads"
    os.makedirs(download_folder, exist_ok=True)

    loop = asyncio.get_running_loop()
    sucesso = await loop.run_in_executor(
        None,
        rodar_selenium,
        usuario,
        senha,
        download_folder
    )

    pdf = get_latest_pdf(download_folder)

    if sucesso and pdf:
        with open(pdf, "rb") as f:
            await update.message.reply_document(f)
        await update.message.reply_text("Aqui está seu PDF!")
    else:
        await update.message.reply_text("Erro ao gerar o PDF.")

    return ConversationHandler.END


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelado.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def main():
    token = os.getenv("BOT_TOKEN")

    ap
