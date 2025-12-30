import os
import glob
import time
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
    latest_pdf = max(pdf_files, key=os.path.getctime)
    return latest_pdf

def rodar_selenium(usuario, senha, download_folder):
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    # chrome_options.add_argument("--headless")
    prefs = {"download.default_directory": download_folder}
    chrome_options.add_experimental_option("prefs", prefs)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    erro_ocorrido = False
    try:
        driver.get("https://sistema.seia.ba.gov.br/")
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "j_username")))

        # Fechar popup de lembretes, se existir
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.ID, "_dialogAlertaIndex_modal")))
            driver.execute_script("""
                var modal = document.getElementById('_dialogAlertaIndex_modal');
                if (modal) { modal.remove(); }
                var dialog = document.getElementById('_dialogAlertaIndex');
                if (dialog) { dialog.remove(); }
            """)
            time.sleep(1)
        except:
            pass

        # Login
        driver.find_element(By.ID, "j_username").send_keys(usuario)
        driver.find_element(By.ID, "j_password").send_keys(senha)
        driver.find_element(By.ID, "btnEntrar").click()

        # Esperar o menu principal aparecer
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, "//a[contains(text(), 'Cadastro')]")))

        # Clicar no menu Cadastro
        cadastro_menu = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Cadastro')]"))
        )
        cadastro_menu.click()

        # Agora clicar em "Imóvel Rural - CEFIR"
        imovel_rural_cefir = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Imóvel Rural - CEFIR"))
        )
        imovel_rural_cefir.click()

        # Esperar carregar a página nova
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "filtroImoveis:j_idt266"))
        )

        # ---- Selecionar Monte Santo ----
        localidade_dropdown = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.ID, "filtroImoveis:j_idt266"))
        )
        localidade_dropdown.click()
        time.sleep(1)  # Pequeno delay para o dropdown abrir

        monte_santo_option = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//li[contains(normalize-space(.), 'Monte Santo')]"))
        )
        monte_santo_option.click()

        # Aguardar carregamento AJAX após seleção da localidade
        WebDriverWait(driver, 30).until(
            EC.invisibility_of_element_located((By.ID, "statusDialog"))
        )

        # ---- Verificar se botão 'Consultar' está dentro de iframe ----
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        encontrou_botao = False
        for i, iframe in enumerate(iframes):
            driver.switch_to.frame(iframe)
            try:
                botao_consultar = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "filtroImoveis:btnConsulta"))
                )
                encontrou_botao = True
                break
            except:
                driver.switch_to.default_content()
        if not encontrou_botao:
            driver.switch_to.default_content()
            botao_consultar = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.ID, "filtroImoveis:btnConsulta"))
            )

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_consultar)
        time.sleep(1)
        try:
            botao_consultar.click()
        except Exception as e:
            driver.execute_script("arguments[0].click();", botao_consultar)

        WebDriverWait(driver, 90).until(
            EC.invisibility_of_element_located((By.ID, "statusDialog"))
        )

        # Esperar o botão 'Ações' aparecer e ser clicável
        botao_acoes = WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "span.ui-row-toggler.ui-icon.ui-icon-circle-triangle-e"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_acoes)
        time.sleep(1)
        botao_acoes.click()
        time.sleep(2)

        # Esperar o botão para baixar o PDF aparecer
        botao_pdf = WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.XPATH, "//img[@title='Visualizar Termo de Compromisso']"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_pdf)
        time.sleep(1)
        botao_pdf.click()
        time.sleep(7)  # Espera o download terminar

    except Exception as e:
        print(f"Erro no Selenium: {e}")
        erro_ocorrido = True
    finally:
        driver.quit()
    return not erro_ocorrido

# Handlers do Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Bem-vindo! Por favor, envie seu usuário:')
    return USUARIO

async def receber_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['usuario'] = update.message.text
    await update.message.reply_text('Agora envie sua senha:')
    return SENHA

async def receber_senha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['senha'] = update.message.text
    await update.message.reply_text('Processando, aguarde...')

    usuario = context.user_data['usuario']
    senha = context.user_data['senha']

    download_folder = os.path.join(os.path.expanduser("~"), "Downloads")
    sucesso = rodar_selenium(usuario, senha, download_folder)

    latest_pdf = get_latest_pdf(download_folder)
    if sucesso and latest_pdf:
        with open(latest_pdf, "rb") as f:
            await update.message.reply_document(f)
        await update.message.reply_text('Aqui está seu PDF!')
    else:
        await update.message.reply_text('Erro ao baixar ou encontrar o PDF.')

    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Cancelado.', reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    application = ApplicationBuilder().token("7517132027:AAHZ-0r-8fLqZx-p2iV2EC4lIHR-fTZ8lU4").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            USUARIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_usuario)],
            SENHA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_senha)],
        },
        fallbacks=[CommandHandler('cancel', cancelar)]
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
