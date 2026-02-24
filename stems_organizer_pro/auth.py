import os
import json
import logging
from .config import APP_DATA_PATH

logger = logging.getLogger(__name__)
SESSION_FILE = os.path.join(APP_DATA_PATH, 'session.json')

class AuthManager:
    """Gerencia autenticação e sessão com o Supabase"""
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.user = None
        self.session = None

    def attempt_auto_login(self):
        """Tenta carregar a sessão anterior do disco usando o Access Token"""
        if not self.supabase or not os.path.exists(SESSION_FILE):
            return False
            
        try:
            with open(SESSION_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                access_token = data.get('access_token')
                refresh_token = data.get('refresh_token')
                
                if access_token and refresh_token:
                    # Restaurar sessão
                    resp = self.supabase.auth.set_session(access_token, refresh_token)
                    if hasattr(resp, 'user'):
                        self.user = resp.user
                        self.session = resp.session
                        return True
        except Exception as e:
            logger.debug(f"Auto-login falhou (possivelmente token expirado): {e}")
            self.logout()  # Limpar arquivo sujo
            
        return False

    def login(self, email, password):
        """Faz o login com e-mail e senha e salva a sessão no disco"""
        if not self.supabase:
            return False, "Banco de dados indisponível no momento."
            
        try:
            resp = self.supabase.auth.sign_in_with_password({"email": email, "password": password})
            if hasattr(resp, 'user') and resp.user:
                self.user = resp.user
                self.session = resp.session
                self._save_session(self.session)
                return True, None
            return False, "O servidor não retornou os dados do usuário."
        except Exception as e:
            logger.error(f"Erro no login: {e}")
            return False, str(e)

    def register(self, email, password):
        """Cria um novo usuário"""
        if not self.supabase:
            return False, "Banco de dados indisponível no momento."
            
        try:
            resp = self.supabase.auth.sign_up({"email": email, "password": password})
            # O status depends if email confirmation is enabled in Supabase settings
            if hasattr(resp, 'user') and resp.user:
                return True, "Conta criada com sucesso! Faça login abaixo."
            return False, "Erro ao criar usuário, tente novamente."
        except Exception as e:
            logger.error(f"Erro no registro: {e}")
            return False, str(e)

    def logout(self):
        """Faz logoff e limpa caches"""
        if self.supabase:
            try:
                self.supabase.auth.sign_out()
            except:
                pass
                
        self.user = None
        self.session = None
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)

    def _save_session(self, session):
        """Salva a sessão em JSON para auto-login"""
        try:
            if not session:
                return
            data = {
                'access_token': session.access_token,
                'refresh_token': session.refresh_token
            }
            with open(SESSION_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception as e:
            logger.error(f"Falha ao salvar a sessão de login: {e}")

    def fetch_user_api_key(self):
        """Busca a chave API (api_key_gemini) da tabela users_profile no Supabase"""
        if not self.supabase or not self.user:
            return None
        try:
            resp = self.supabase.table('users_profile').select('api_key_gemini').eq('id', self.user.id).execute()
            if resp.data and len(resp.data) > 0:
                key = resp.data[0].get('api_key_gemini')
                if key and len(key) > 20:
                    return key
        except Exception as e:
            logger.error(f"Falha ao puxar api_key_gemini: {e}")
        return None

    def save_user_api_key(self, api_key):
        """Salva (Upsert) a chave API (api_key_gemini) na tabela users_profile"""
        if not self.supabase or not self.user:
            return False
        try:
            # Em SQL 'upsert' funciona baseado na primary key (id)
            self.supabase.table('users_profile').upsert({
                'id': self.user.id,
                'email': self.user.email,
                'api_key_gemini': api_key
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Falha ao salvar api_key_gemini: {e}")
            return False

    def login_with_google(self, callback_func):
        """Inicia fluxo de OAuth com o Google rodando um servidor temporario para captura do callback"""
        if not self.supabase:
            return False, "Supabase não configurado."
            
        import threading
        import webbrowser
        from http.server import BaseHTTPRequestHandler, HTTPServer
        import urllib.parse
        
        # Resposta do servidor OAuth
        auth_code = {"code": None, "error": None}
        
        class OAuthCallbackHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass
                
            def do_GET(self):
                parsed_path = urllib.parse.urlparse(self.path)
                query_params = urllib.parse.parse_qs(parsed_path.query)
                
                if 'code' in query_params:
                    auth_code['code'] = query_params['code'][0]
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    html_success = """
                    <!DOCTYPE html>
                    <html lang="pt-BR">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>Login Efetuado</title>
                        <style>
                            body { background-color: #1a1a2e; color: #e1e1e6; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                            .container { background-color: #24243e; padding: 40px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.5); text-align: center; border: 1px solid #363650; max-width: 400px; }
                            h1 { color: #00e5ff; margin-bottom: 10px; }
                            p { color: #a0a0b0; font-size: 16px; line-height: 1.5; }
                            .icon { font-size: 48px; margin-bottom: 15px; }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="icon">✅</div>
                            <h1>Login Concluído!</h1>
                            <p>Autenticação com o Google realizada com sucesso.</p>
                            <p>Você já pode fechar esta aba com segurança e voltar para o <b>Stems Organizer PRO</b>.</p>
                        </div>
                    </body>
                    </html>
                    """
                    self.wfile.write(html_success.encode('utf-8'))
                else:
                    auth_code['error'] = query_params.get('error_description', ['Erro desconhecido'])[0]
                    self.send_response(400)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.end_headers()
                    
                    error_msg = auth_code['error']
                    html_error = f"""
                    <!DOCTYPE html>
                    <html lang="pt-BR">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>Erro no Login</title>
                        <style>
                            body {{ background-color: #1a1a2e; color: #e1e1e6; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
                            .container {{ background-color: #24243e; padding: 40px; border-radius: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.5); text-align: center; border: 1px solid #ff4444; max-width: 400px; }}
                            h1 {{ color: #ff4444; margin-bottom: 10px; }}
                            p {{ color: #a0a0b0; font-size: 16px; line-height: 1.5; }}
                            .icon {{ font-size: 48px; margin-bottom: 15px; }}
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="icon">❌</div>
                            <h1>Erro na Autenticação</h1>
                            <p>Não foi possível concluir o login com o Google.</p>
                            <p>Motivo: {error_msg}</p>
                            <p>Por favor, feche esta aba e tente novamente no aplicativo.</p>
                        </div>
                    </body>
                    </html>
                    """
                    self.wfile.write(html_error.encode('utf-8'))
                    
                # Encerrar servidor loopback após captura
                threading.Thread(target=self.server.shutdown).start()

        def run_server_and_exchange():
            server = HTTPServer(('127.0.0.1', 54321), OAuthCallbackHandler)
            try:
                # Obter a URL de autenticação via SDK do Supabase usando PKCE
                res = self.supabase.auth.sign_in_with_oauth({
                    'provider': 'google',
                    'options': {
                        'redirect_to': 'http://127.0.0.1:54321/callback',
                        'skip_browser_redirect': True # Queremos nós mesmos abrir o browser
                    }
                })
                
                # O SDK retorna a URL pronta. Vamos abrir.
                webbrowser.open(res.url)
            except Exception as e:
                callback_func(False, f"Falha ao gerar URL OAuth: {e}")
                return
                
            # Manter servidor ouvindo até o callback
            server.serve_forever()
            
            # Se chegou aqui, server rodou e desligou.
            if auth_code['code']:
                try:
                    # Trocar o código pelo access token real do Supabase
                    resp = self.supabase.auth.exchange_code_for_session({"auth_code": auth_code['code']})
                    if hasattr(resp, 'user') and resp.user:
                        self.user = resp.user
                        self.session = resp.session
                        self._save_session(self.session)
                        callback_func(True, None)
                    else:
                        callback_func(False, "Falha ao obter dados do usuário via Google.")
                except Exception as e:
                    logger.error(f"Erro ao trocar token OAuth: {e}")
                    callback_func(False, f"Erro interno OAuth: {e}")
            else:
                callback_func(False, auth_code['error'] or "Login cancelado pela aba ou timeout.")

        # Rodar numa thread paralela para não congelar a UI do Tkinter
        t = threading.Thread(target=run_server_and_exchange)
        t.daemon = True
        t.start()
        
        return True, "Aguardando resposta do navegador..."
