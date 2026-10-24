# 🏰 Disney+ Code Stream (ConectaEmail)

Sistema web em tempo real que monitora sua caixa de entrada do Gmail via conexão segura IMAP para capturar códigos de acesso único / verificação enviados pela **Disney+**, exibindo-os com contagem regressiva de **15 minutos**, botão de cópia instantânea e alerta sonoro.

---

## 🚀 Como Iniciar Rápido

### Método 1: Dois cliques (Mais fácil)
Basta dar dois cliques no arquivo **`iniciar.bat`**. Ele abrirá o navegador em `http://localhost:5000` e iniciará o servidor automaticamente.

### Método 2: Via Terminal (PowerShell / CMD)
```powershell
# Ativar o ambiente virtual e rodar o servidor
.\.venv\Scripts\python.exe app.py
```
Acesse no seu navegador: **[http://localhost:5000](http://localhost:5000)**

---

## 🔑 Configuração do Gmail (Senha de Aplicativo)

Para que o sistema leia sua caixa de entrada de forma segura sem usar sua senha pessoal da conta Google:

1. **Ative a verificação em 2 etapas** na sua Conta Google (se ainda não estiver ativa).
2. Acesse a página de senhas de app do Google:  
   👉 **[https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)**
3. Digite um nome para a aplicação (exemplo: `ConectaEmail` ou `Disney`) e clique em **Criar**.
4. O Google vai exibir uma senha de **16 letras** (ex: `abcd efgh ijkl mnop`).
5. Abra o arquivo **`.env`** no diretório do projeto e preencha:
   ```env
   EMAIL_USER=seu_email@gmail.com
   EMAIL_PASS=abcd efgh ijkl mnop
   ```
6. Salve o arquivo `.env`. Clique no botão **"Recarregar .env"** no site ou reinicie o aplicativo.

---

## ✨ Funcionalidades

- **Monitoramento IMAP Contínuo**: Verifica novos e-mails automaticamente a cada 10 segundos em segundo plano (sem travar a interface).
- **Extração Inteligente**: Reconhece e-mails da Disney/Disney+ tanto em português (*"Seu código de acesso único é..."*) quanto em inglês (*"Your one-time passcode..."*), em texto puro e em HTML.
- **Janela de 15 Minutos**:
  - Exibe o código ativo em 6 caixas de dígitos grandes e iluminadas.
  - Barra de progresso e relógio decrescente em tempo real (`MM:SS restantes`).
  - Alerta visual avermelhado quando restar menos de 2 minutos.
  - Muda para estado "Expirado" assim que os 15 minutos terminam.
- **Cópia em 1 Clique**: Botão gigante de cópia com feedback visual ("Copiado!") e notificação toast.
- **Efeito Sonoro Disney**: Toca um sino suave sintetizado via Web Audio API quando um novo código chega.
- **Botão de Simulação**: Permite testar todo o fluxo visual (código, contador de 15 minutos e som) imediatamente com o botão *"Simular Teste"*.
- **Histórico**: Armazena os últimos códigos recebidos e seus status.
