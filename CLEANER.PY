
"""
Image Cleaner ASL - Versão Final
Data: 2024
"""

import sys
import os
import re
import threading
import traceback
import shutil
import sqlite3
import pyodbc
from datetime import datetime, date
from typing import Optional, Dict, List, Any

# PySide6 imports
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QTextEdit,
    QDateEdit, QProgressBar, QMessageBox, QVBoxLayout, QHBoxLayout, QGroupBox,
    QGridLayout, QSizePolicy, QSpacerItem, QComboBox, QTabWidget, QFrame,
    QCheckBox, QLineEdit, QFileDialog, QDialog, QListWidget, QListWidgetItem,
    QFormLayout, QDialogButtonBox, QMenuBar, QMenu, QPlainTextEdit,
    QInputDialog, QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, QDate, Signal, QObject, QTimer, QSize
from PySide6.QtGui import QFont, QColor, QTextCursor, QAction, QIcon, QPixmap

# =====================
# CONFIGURAÇÃO DE ENCODING PARA WINDOWS
# =====================

# Configurar encoding para Windows
if sys.platform == "win32":
    import codecs
    # Verifica se stdout tem 'buffer'
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

# =====================
# FUNÇÕES DE CAMINHO
# =====================

def get_app_directory():
    """Retorna o diretório onde o aplicativo está sendo executado"""
    if getattr(sys, 'frozen', False):
        # Se estiver rodando como executável (pyinstaller)
        return os.path.dirname(sys.executable)
    else:
        # Se estiver rodando como script Python
        return os.path.dirname(os.path.abspath(__file__))

def get_logs_directory():
    """Retorna o diretório de logs (cria se não existir)"""
    logs_dir = os.path.join(get_app_directory(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir

# =====================
# CONFIGURAÇÃO DE LOGS
# =====================

LOG_PATH = get_logs_directory()
LOG_FILE = os.path.join(LOG_PATH, "log.txt")
DB_LOG_FILE = os.path.join(LOG_PATH, "db_log.txt")

class SignalEmitter(QObject):
    log_signal = Signal(str, str, bool)
    progress_signal = Signal(int)
    status_signal = Signal(str)
    enable_clean_signal = Signal(bool)
    config_updated = Signal()

emitter = SignalEmitter()

def write_log(message: str, level: str = "INFO", database: bool = False):
    """Escreve log em arquivo na pasta de logs do executável"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] [{level}] {message}\n"
    
    # Escrever em arquivo
    try:
        path = DB_LOG_FILE if database else LOG_FILE
        with open(path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"Falha ao escrever log: {e}", file=sys.stderr)
    
    # Emitir para GUI
    emitter.log_signal.emit(message, level, database)

# =====================
# DATABASE MANAGER (SQLite)
# =====================

class DatabaseManager:
    """Gerencia o banco de dados SQLite com caminhos relativos"""
    
    def __init__(self, db_path: str = None):
        # Se não especificar caminho, usa o diretório do executável
        if db_path is None:
            db_path = os.path.join(get_app_directory(), "Cleaner.db3")
        
        self.db_path = db_path
        print(f"DEBUG: Inicializando DatabaseManager em: {db_path}")
        print(f"DEBUG: Caminho absoluto: {os.path.abspath(db_path)}")
        self.init_database()
    
    def get_connection(self):
        """Retorna conexão com o banco"""
        # Garantir que o diretório existe
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Inicializa o banco se não existir"""
        try:
            # Criar diretório se não existir
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # ========== TABELA USUÁRIOS ==========
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    login TEXT UNIQUE NOT NULL,
                    senha TEXT NOT NULL,
                    nome_completo TEXT,
                    nivel_acesso TEXT DEFAULT 'operador' CHECK (nivel_acesso IN ('operador', 'supervisor', 'administrador')),
                    ativo INTEGER DEFAULT 1,
                    data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                    ultimo_login DATETIME
                )
            ''')
            
            # ========== TABELA CONFIGURAÇÕES ==========
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS configuracoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chave TEXT UNIQUE NOT NULL,
                    valor TEXT,
                    descricao TEXT,
                    categoria TEXT DEFAULT 'geral',
                    data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # ========== TABELA CONEXÕES BANCO ==========
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conexao_banco (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome_conexao TEXT NOT NULL,
                    string_conexao TEXT NOT NULL,
                    padrao INTEGER DEFAULT 0,
                    ativo INTEGER DEFAULT 1,
                    data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # ========== TABELA LOGS ==========
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs_atividade (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario_id INTEGER,
                    acao TEXT NOT NULL,
                    modulo TEXT NOT NULL,
                    detalhes TEXT,
                    ip TEXT,
                    data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
                )
            ''')
            
            # ========== ÍNDICES ==========
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_usuarios_login ON usuarios(login)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_configuracoes_chave ON configuracoes(chave)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_conexao_banco_padrao ON conexao_banco(padrao)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_logs_atividade_data ON logs_atividade(data_hora)')
            
            # Trigger para garantir apenas uma conexão padrão
            cursor.execute('''
                CREATE TRIGGER IF NOT EXISTS trg_uma_conexao_padrao
                AFTER UPDATE OF padrao ON conexao_banco
                WHEN NEW.padrao = 1
                BEGIN
                    UPDATE conexao_banco 
                    SET padrao = 0 
                    WHERE id != NEW.id AND padrao = 1;
                END
            ''')
            
            # ========== DADOS INICIAIS ==========
            # Usuário admin se não existir
            cursor.execute("SELECT COUNT(*) FROM usuarios WHERE login = 'admin'")
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT INTO usuarios (login, senha, nome_completo, nivel_acesso)
                    VALUES (?, ?, ?, ?)
                ''', ('admin', '123', 'Administrador do Sistema', 'administrador'))
                write_log("Usuário admin criado no banco de dados", "INFO")
            else:
                # Atualizar senha do admin para '123' se já existir
                cursor.execute("UPDATE usuarios SET senha = '123' WHERE login = 'admin'")
                write_log("Senha do usuário admin atualizada para '123'", "INFO")
            
            # Configuração padrão do caminho das imagens
            cursor.execute("SELECT COUNT(*) FROM configuracoes WHERE chave = 'path_imagens'")
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT INTO configuracoes (chave, valor, descricao, categoria)
                    VALUES (?, ?, ?, ?)
                ''', ('path_imagens', 'C:\\IMAGENS_PRINTER', 'Caminho das pastas de imagens', 'pastas'))
            
            # Conexão padrão se não existir
            cursor.execute("SELECT COUNT(*) FROM conexao_banco WHERE padrao = 1")
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT INTO conexao_banco (nome_conexao, string_conexao, padrao)
                    VALUES (?, ?, ?)
                ''', (
                    'Produção',
                    'DRIVER={ODBC Driver 17 for SQL Server};SERVER=MEU_SERVIDOR;DATABASE=Printer;UID=sa;PWD=SUA_SENHA;',
                    1
                ))
            
            conn.commit()
            
            # DEBUG: Verificar todos os usuários
            print("DEBUG: Verificando usuários no banco após inicialização:")
            cursor.execute("SELECT id, login, senha, nome_completo, nivel_acesso, ativo FROM usuarios")
            users = cursor.fetchall()
            for user in users:
                print(f"  ID: {user[0]}, Login: '{user[1]}', Senha: '{user[2]}', Nome: '{user[3]}', Nível: {user[4]}, Ativo: {user[5]}")
            
            conn.close()
            
            write_log(f"Banco de dados inicializado em: {self.db_path}", "INFO")
            
        except Exception as e:
            write_log(f"Erro ao inicializar banco: {e}", "ERROR")
            print(f"DEBUG: Erro ao inicializar banco: {e}")
            traceback.print_exc()
    
    # ========== MÉTODOS DE USUÁRIOS ==========
    
    def autenticar_usuario(self, login: str, senha: str) -> Optional[Dict]:
        """Autentica usuário com senha em texto puro"""
        print(f"DEBUG: autenticar_usuario chamado com login='{login}', senha='{senha}'")
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, login, nome_completo, nivel_acesso, ativo
                FROM usuarios 
                WHERE login = ? AND senha = ? AND ativo = 1
            ''', (login, senha))
            
            user = cursor.fetchone()
            conn.close()
            
            print(f"DEBUG: Resultado da consulta: {user}")
            
            if user:
                # Atualizar último login
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE usuarios SET ultimo_login = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (user['id'],))
                conn.commit()
                conn.close()
                
                result = dict(user)
                print(f"DEBUG: Usuário autenticado: {result}")
                return result
            
            print(f"DEBUG: Nenhum usuário encontrado com login='{login}' e senha='{senha}'")
            return None
            
        except Exception as e:
            write_log(f"Erro na autenticação: {e}", "ERROR")
            print(f"DEBUG: Erro na autenticação: {e}")
            return None
    
    def criar_usuario(self, login: str, senha: str, nome_completo: str, nivel: str = "operador") -> bool:
        """Cria novo usuário"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO usuarios (login, senha, nome_completo, nivel_acesso)
                VALUES (?, ?, ?, ?)
            ''', (login, senha, nome_completo, nivel))
            
            conn.commit()
            conn.close()
            return True
            
        except sqlite3.IntegrityError:
            return False  # Usuário já existe
        except Exception as e:
            write_log(f"Erro ao criar usuário: {e}", "ERROR")
            return False
    
    def obter_usuarios(self) -> List[Dict]:
        """Retorna todos os usuários"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, login, nome_completo, nivel_acesso, ativo, 
                       data_criacao, ultimo_login
                FROM usuarios
                ORDER BY nome_completo
            ''')
            
            users = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return users
            
        except Exception as e:
            write_log(f"Erro ao buscar usuários: {e}", "ERROR")
            return []
    
    def atualizar_usuario(self, user_id: int, **kwargs) -> bool:
        """Atualiza dados do usuário"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            sets = []
            params = []
            for key, value in kwargs.items():
                sets.append(f"{key} = ?")
                params.append(value)
            
            params.append(user_id)
            cursor.execute(f'''
                UPDATE usuarios SET {', '.join(sets)}
                WHERE id = ?
            ''', params)
            
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
            
        except Exception as e:
            write_log(f"Erro ao atualizar usuário: {e}", "ERROR")
            return False
    
    def excluir_usuario(self, user_id: int) -> bool:
        """Exclui um usuário (desativa)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('UPDATE usuarios SET ativo = 0 WHERE id = ?', (user_id,))
            
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
            
        except Exception as e:
            write_log(f"Erro ao excluir usuário: {e}", "ERROR")
            return False
    
    # ========== MÉTODOS DE CONFIGURAÇÕES ==========
    
    def salvar_config(self, chave: str, valor: Any, descricao: str = None, categoria: str = "geral") -> bool:
        """Salva configuração"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO configuracoes (chave, valor, descricao, categoria, data_atualizacao)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (chave, str(valor), descricao, categoria))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            write_log(f"Erro ao salvar configuração: {e}", "ERROR")
            return False
    
    def obter_config(self, chave: str, default: Any = None) -> Any:
        """Obtém configuração"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT valor FROM configuracoes WHERE chave = ?', (chave,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                valor = result['valor']
                # Tentar converter tipos
                if valor.isdigit():
                    return int(valor)
                elif valor.replace('.', '', 1).isdigit():
                    return float(valor)
                elif valor.lower() in ('true', 'false'):
                    return valor.lower() == 'true'
                return valor
            
            return default
            
        except Exception as e:
            write_log(f"Erro ao obter configuração: {e}", "ERROR")
            return default
    
    def obter_todas_configs(self) -> Dict[str, Any]:
        """Retorna todas as configurações"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT chave, valor FROM configuracoes')
            configs = {row['chave']: row['valor'] for row in cursor.fetchall()}
            conn.close()
            return configs
            
        except Exception as e:
            write_log(f"Erro ao buscar configurações: {e}", "ERROR")
            return {}
    
    # ========== MÉTODOS DE CONEXÕES BANCO ==========
    
    def salvar_conexao_banco(self, nome: str, string_conexao: str, padrao: bool = False) -> bool:
        """Salva conexão com banco"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if padrao:
                # Desmarca outras como padrão
                cursor.execute('UPDATE conexao_banco SET padrao = 0')
            
            cursor.execute('''
                INSERT OR REPLACE INTO conexao_banco 
                (nome_conexao, string_conexao, padrao, data_criacao)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (nome, string_conexao, 1 if padrao else 0))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            write_log(f"Erro ao salvar conexão: {e}", "ERROR")
            return False
    
    def obter_conexoes(self) -> List[Dict]:
        """Retorna todas as conexões"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, nome_conexao, string_conexao, padrao
                FROM conexao_banco
                WHERE ativo = 1
                ORDER BY padrao DESC, nome_conexao
            ''')
            
            conexoes = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return conexoes
            
        except Exception as e:
            write_log(f"Erro ao buscar conexões: {e}", "ERROR")
            return []
    
    def obter_conexao_padrao(self) -> Optional[Dict]:
        """Obtém conexão padrão"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, nome_conexao, string_conexao
                FROM conexao_banco
                WHERE padrao = 1 AND ativo = 1
                LIMIT 1
            ''')
            
            result = cursor.fetchone()
            conn.close()
            
            return dict(result) if result else None
            
        except Exception as e:
            write_log(f"Erro ao obter conexão padrão: {e}", "ERROR")
            return None
    
    def excluir_conexao(self, conexao_id: int) -> bool:
        """Exclui uma conexão (desativa)"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('UPDATE conexao_banco SET ativo = 0 WHERE id = ?', (conexao_id,))
            
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
            
        except Exception as e:
            write_log(f"Erro ao excluir conexão: {e}", "ERROR")
            return False
    
    # ========== MÉTODOS DE LOGS ==========
    
    def registrar_log(self, usuario_id: int, acao: str, modulo: str, detalhes: str = None):
        """Registra log de atividade"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO logs_atividade (usuario_id, acao, modulo, detalhes)
                VALUES (?, ?, ?, ?)
            ''', (usuario_id, acao, modulo, detalhes))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            write_log(f"Erro ao registrar log: {e}", "ERROR")
    
    def obter_logs(self, limit: int = 100) -> List[Dict]:
        """Obtém logs recentes"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT l.*, u.login, u.nome_completo
                FROM logs_atividade l
                LEFT JOIN usuarios u ON l.usuario_id = u.id
                ORDER BY l.data_hora DESC
                LIMIT ?
            ''', (limit,))
            
            logs = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return logs
            
        except Exception as e:
            write_log(f"Erro ao buscar logs: {e}", "ERROR")
            return []

# =====================
# FUNÇÕES DE ANÁLISE E LIMPEZA
# =====================

FOLDER_NAME_REGEX = re.compile(r"^(\d{8})\s(\d{4})$")

def convert_from_asl_date_format(folder_name: str):
    """Converte nome de pasta no formato YYYYDDMM HHmm para datetime.date"""
    m = FOLDER_NAME_REGEX.match(folder_name)
    if not m:
        return None
    date_part = m.group(1)
    try:
        year = int(date_part[0:4])
        day = int(date_part[4:6])
        month = int(date_part[6:8])
        dt = datetime(year, month, day)
        return dt.date()
    except Exception:
        return None

def test_asl_folder_name(folder_name: str) -> bool:
    return bool(FOLDER_NAME_REGEX.match(folder_name))

def get_folder_statistics(path: str, start_date: date, end_date: date, 
                         db_manager: DatabaseManager = None, usuario_id: int = None):
    """Analisa pastas e registra no log de atividades"""
    write_log(f"Analisando pasta: {path}", "INFO")
    write_log(f"Periodo: {start_date.strftime('%d/%m/%Y')} a {end_date.strftime('%d/%m/%Y')}", "INFO")
    
    if db_manager and usuario_id:
        db_manager.registrar_log(usuario_id, "ANALISE_PASTAS", "Limpeza", 
                               f"Periodo: {start_date} a {end_date}")

    if not os.path.exists(path):
        write_log(f"ERRO: Pasta nao encontrada: {path}", "ERROR")
        return []

    try:
        folders = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]
    except Exception as e:
        write_log(f"ERRO ao listar pastas: {e}", "ERROR")
        return []

    matched = []
    total_folders = len(folders)
    for idx, folder in enumerate(folders):
        # Atualizar progresso
        if total_folders > 0:
            progress = int((idx + 1) / total_folders * 100)
            emitter.progress_signal.emit(progress)
        
        if test_asl_folder_name(folder):
            folder_date = convert_from_asl_date_format(folder)
            if folder_date is None:
                continue
            if start_date <= folder_date <= end_date:
                full = os.path.join(path, folder)
                size_bytes = 0
                try:
                    for root, _, files in os.walk(full):
                        for f in files:
                            fp = os.path.join(root, f)
                            try:
                                size_bytes += os.path.getsize(fp)
                            except Exception:
                                pass
                except Exception as e:
                    write_log(f"Aviso ao calcular tamanho {folder}: {e}", "WARNING")
                size_mb = round(size_bytes / (1024*1024), 2)
                matched.append({
                    'Name': folder,
                    'FullName': full,
                    'Date': folder_date,
                    'Size': size_mb
                })

    write_log(f"Pastas encontradas: {len(matched)}", "SUCCESS")
    return matched

def test_database_connection(connection_string: str) -> bool:
    """Testa conexao com SQL Server"""
    try:
        conn = pyodbc.connect(connection_string, timeout=5)
        conn.close()
        return True
    except Exception as e:
        write_log(f"Falha conexao DB: {e}", "DB_ERROR", database=True)
        return False

def get_database_statistics(connection_string: str, start_date: datetime, end_date: datetime):
    """Obtem estatisticas do banco SQL Server"""
    results = {}
    try:
        conn = pyodbc.connect(connection_string)
        cur = conn.cursor()
        query = """
        SELECT 
            (SELECT COUNT(*) FROM [Printer].[dbo].[JOBS] WHERE Jobdatetime >= ? AND Jobdatetime <= ?) as JobsCount,
            (SELECT COUNT(*) FROM [Printer].[dbo].[JOBs_Detail] WHERE JOBID IN (SELECT JOBID FROM [Printer].[dbo].[JOBS] WHERE Jobdatetime >= ? AND Jobdatetime <= ?)) as DetailsCount,
            (SELECT COUNT(*) FROM [Printer].[dbo].[JOB_HISTORICO] WHERE JOBID IN (SELECT JOBID FROM [Printer].[dbo].[JOBS] WHERE Jobdatetime >= ? AND Jobdatetime <= ?)) as HistoryCount
        """
        params = (start_date, end_date, start_date, end_date, start_date, end_date)
        cur.execute(query, params)
        row = cur.fetchone()
        if row:
            results['JobsCount'] = row[0]
            results['DetailsCount'] = row[1]
            results['HistoryCount'] = row[2]
        cur.close()
        conn.close()
        write_log(f"Banco: Jobs={results.get('JobsCount',0)}, Details={results.get('DetailsCount',0)}, History={results.get('HistoryCount',0)}", "DB_INFO", database=True)
        return results
    except Exception as e:
        write_log(f"ERRO ao obter estatisticas do banco: {e}", "DB_ERROR", database=True)
        return None

def execute_database_cleanup(connection_string: str, start_date: datetime, end_date: datetime, 
                           db_manager: DatabaseManager = None, usuario_id: int = None):
    """Executa limpeza do banco SQL Server"""
    results = {'JobsDeleted': 0, 'DetailsDeleted': 0, 'HistoryDeleted': 0, 'Success': False}
    
    if db_manager and usuario_id:
        db_manager.registrar_log(usuario_id, "INICIO_LIMPEZA_BANCO", "Limpeza", 
                               f"Periodo: {start_date} a {end_date}")
    
    try:
        conn = pyodbc.connect(connection_string, autocommit=False)
        cur = conn.cursor()
        write_log("Iniciando transacao no banco...", "DB_INFO", database=True)

        try:
            q1 = "DELETE FROM [Printer].[dbo].[JOB_HISTORICO] WHERE JOBID IN (SELECT jobid FROM [Printer].[dbo].[JOBS] WHERE Jobdatetime >= ? AND Jobdatetime <= ?)"
            cur.execute(q1, (start_date, end_date))
            results['HistoryDeleted'] = cur.rowcount
            
            q2 = "DELETE FROM [Printer].[dbo].[JOBs_Detail] WHERE JOBID IN (SELECT jobid FROM [Printer].[dbo].[JOBS] WHERE Jobdatetime >= ? AND Jobdatetime <= ?)"
            cur.execute(q2, (start_date, end_date))
            results['DetailsDeleted'] = cur.rowcount
            
            q3 = "DELETE FROM [Printer].[dbo].[JOBS] WHERE Jobdatetime >= ? AND Jobdatetime <= ?"
            cur.execute(q3, (start_date, end_date))
            results['JobsDeleted'] = cur.rowcount

            conn.commit()
            results['Success'] = True
            
            if db_manager and usuario_id:
                db_manager.registrar_log(usuario_id, "CONCLUSAO_LIMPEZA_BANCO", "Limpeza",
                                      f"Jobs: {results['JobsDeleted']}, Detalhes: {results['DetailsDeleted']}, Historico: {results['HistoryDeleted']}")
            
            write_log("Transacao concluida com sucesso!", "DB_SUCCESS", database=True)
        except Exception as inner:
            conn.rollback()
            write_log(f"ERRO na transacao. Rollback executado: {inner}", "DB_ERROR", database=True)
            raise
        finally:
            cur.close()
            conn.close()
        return results
    except Exception as e:
        write_log(f"ERRO na limpeza do banco: {e}", "DB_ERROR", database=True)
        results['Success'] = False
        return results

def delete_folders(folders_list, db_manager: DatabaseManager = None, usuario_id: int = None):
    """Exclui pastas e registra no log"""
    deleted = 0
    errors = 0
    total = len(folders_list)
    
    if db_manager and usuario_id:
        db_manager.registrar_log(usuario_id, "INICIO_EXCLUSAO_PASTAS", "Limpeza",
                               f"Total de pastas: {total}")
    
    for i, folder in enumerate(folders_list):
        try:
            if os.path.exists(folder['FullName']):
                shutil.rmtree(folder['FullName'], ignore_errors=False)
                
                if not os.path.exists(folder['FullName']):
                    deleted += 1
                    write_log(f"Pasta excluida: {folder['Name']} ({folder['Size']} MB)", "SUCCESS")
                else:
                    errors += 1
                    write_log(f"Falha: pasta ainda existe apos exclusao: {folder['Name']}", "ERROR")
            else:
                write_log(f"Pasta nao encontrada: {folder['Name']}", "WARNING")
                errors += 1
                
        except PermissionError as e:
            errors += 1
            write_log(f"Erro de permissao em {folder['Name']}: {e}", "ERROR")
        except Exception as e:
            errors += 1
            write_log(f"Erro ao excluir {folder['Name']}: {e}", "ERROR")
        
        # Atualizar progresso
        if total > 0:
            emitter.progress_signal.emit(int((i + 1) / total * 100))
    
    if db_manager and usuario_id:
        db_manager.registrar_log(usuario_id, "CONCLUSAO_EXCLUSAO_PASTAS", "Limpeza",
                               f"Excluidas: {deleted}, Erros: {errors}")
    
    return deleted, errors

# =====================
# DIÁLOGOS
# =====================

class LoginDialog(QDialog):
    """Dialogo de login usando SQLite"""
    
    login_success = Signal(dict)
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self.setWindowTitle("Login - Image Cleaner ASL")
        self.setFixedSize(400, 350)  # Tamanho ajustado para responsividade
        
        self.setup_ui()
        self.setStyle()
        
        # Tentar auto-login com ultimo usuario
        self.try_auto_login()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)  # Margens ajustadas
        layout.setSpacing(15)  # Espaçamento reduzido
        
        # Logo/Ícone
        icon_frame = QFrame()
        icon_layout = QVBoxLayout(icon_frame)
        icon_label = QLabel("🖥️")
        icon_label.setFont(QFont("Segoe UI", 40))
        icon_label.setAlignment(Qt.AlignCenter)
        icon_layout.addWidget(icon_label)
        layout.addWidget(icon_frame)
        
        # Título
        title = QLabel("Image Cleaner ASL")
        title.setFont(QFont("Segoe UI", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Subtítulo
        subtitle = QLabel("Enterprise Edition")
        subtitle.setFont(QFont("Segoe UI", 11))
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)
        
        # Espaçador
        layout.addSpacing(10)
        
        # Campo de login
        self.login_input = QLineEdit()
        self.login_input.setPlaceholderText("Usuário")
        self.login_input.setMinimumHeight(40)
        self.login_input.setProperty("class", "login-field")
        layout.addWidget(self.login_input)
        
        # Campo de senha
        self.senha_input = QLineEdit()
        self.senha_input.setPlaceholderText("Senha")
        self.senha_input.setEchoMode(QLineEdit.Password)
        self.senha_input.setMinimumHeight(40)
        self.senha_input.setProperty("class", "login-field")
        layout.addWidget(self.senha_input)
        
        # Botão de login
        self.login_btn = QPushButton("ENTRAR")
        self.login_btn.clicked.connect(self.authenticate)
        self.login_btn.setMinimumHeight(45)
        self.login_btn.setProperty("class", "primary-button")
        layout.addWidget(self.login_btn)
        
        # Status (invisível inicialmente)
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
        # Focar no campo de login
        self.login_input.setFocus()
    
    def setStyle(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1d21;
                border-radius: 10px;
            }
            QLabel {
                color: #ffffff;
            }
            QLabel#subtitle {
                color: #9ca3af;
                font-size: 12px;
            }
            QLineEdit.login-field {
                padding: 10px 15px;
                border: 2px solid #374151;
                border-radius: 8px;
                font-size: 14px;
                background-color: #2d3748;
                color: #ffffff;
                selection-background-color: #3b82f6;
            }
            QLineEdit.login-field:focus {
                border: 2px solid #3b82f6;
                background-color: #374151;
            }
            QPushButton.primary-button {
                background-color: #3b82f6;
                color: white;
                border: none;
                padding: 12px;
                border-radius: 8px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton.primary-button:hover {
                background-color: #2563eb;
            }
            QPushButton.primary-button:pressed {
                background-color: #1d4ed8;
            }
            QPushButton.primary-button:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
    
    def try_auto_login(self):
        """Tenta fazer login automatico com ultimo usuario"""
        ultimo_usuario = self.db_manager.obter_config("ultimo_usuario")
        if ultimo_usuario:
            self.login_input.setText(ultimo_usuario)
            self.senha_input.setFocus()
    
    def authenticate(self):
        """Autentica o usuario"""
        login = self.login_input.text().strip()
        senha = self.senha_input.text()
        
        print(f"\n=== DEBUG AUTHENTICATE ===")
        print(f"Login digitado: '{login}'")
        print(f"Senha digitada: '{senha}'")
        print(f"Banco de dados: {self.db_manager.db_path}")
        
        if not login:
            self.show_message("Informe o login.", "error")
            self.login_input.setFocus()
            return
        
        if not senha:
            self.show_message("Informe a senha.", "error")
            self.senha_input.setFocus()
            return
        
        # Desabilitar botão durante autenticação
        self.login_btn.setEnabled(False)
        self.login_btn.setText("AUTENTICANDO...")
        
        # Processar autenticação
        user = self.db_manager.autenticar_usuario(login, senha)
        
        if user:
            # Salvar último usuário
            self.db_manager.salvar_config("ultimo_usuario", login, "Último usuário logado")
            
            # Registrar log de login
            self.db_manager.registrar_log(
                user['id'], "LOGIN", "Sistema", 
                f"Usuário {login} fez login"
            )
            
            self.show_message("Login bem-sucedido!", "success")
            QTimer.singleShot(500, lambda: self.accept_login(user))
        else:
            print("DEBUG: Falha na autenticação")
            # Verificar se o arquivo do banco existe
            if not os.path.exists(self.db_manager.db_path):
                print(f"DEBUG: Arquivo do banco NÃO EXISTE: {self.db_manager.db_path}")
            else:
                print(f"DEBUG: Arquivo do banco EXISTE, tamanho: {os.path.getsize(self.db_manager.db_path)} bytes")
                
                # Verificar todos os usuários no banco
                try:
                    conn = sqlite3.connect(self.db_manager.db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT login, senha, ativo FROM usuarios")
                    all_users = cursor.fetchall()
                    conn.close()
                    
                    print("DEBUG: Usuários no banco:")
                    for user in all_users:
                        print(f"  Login: '{user[0]}', Senha: '{user[1]}', Ativo: {user[2]}")
                except Exception as e:
                    print(f"DEBUG: Erro ao verificar banco: {e}")
            
            self.show_message("Login ou senha inválidos.", "error")
            self.login_btn.setEnabled(True)
            self.login_btn.setText("ENTRAR")
    
    def accept_login(self, user: Dict):
        """Aceita o login e emite sinal"""
        self.login_success.emit(user)
        self.accept()
    
    def show_message(self, message: str, tipo: str):
        """Exibe mensagem de status"""
        self.status_label.setVisible(True)
        
        if tipo == "error":
            self.status_label.setStyleSheet("""
                color: #ef4444; 
                font-weight: bold; 
                background-color: rgba(239, 68, 68, 0.1);
                padding: 8px;
                border-radius: 5px;
                border: 1px solid rgba(239, 68, 68, 0.3);
            """)
        else:
            self.status_label.setStyleSheet("""
                color: #10b981; 
                font-weight: bold; 
                background-color: rgba(16, 185, 129, 0.1);
                padding: 8px;
                border-radius: 5px;
                border: 1px solid rgba(16, 185, 129, 0.3);
            """)
        
        self.status_label.setText(message)


class ConfigSQLDialog(QDialog):
    """Janela para gerenciar conexões SQL Server"""

    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self.setWindowTitle("Conexões SQL Server")
        self.setMinimumSize(600, 450)

        self.setup_ui()
        self.load_connections()
        self.apply_style()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Título
        title = QLabel("Gerenciador de Conexões SQL Server")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Lista de conexões
        self.conn_list = QListWidget()
        self.conn_list.setSelectionMode(QListWidget.SingleSelection)
        self.conn_list.setMinimumHeight(200)
        layout.addWidget(self.conn_list, 1)

        # Botões de ação
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.add_btn = QPushButton("➕ Adicionar")
        self.edit_btn = QPushButton("✏️ Editar")
        self.remove_btn = QPushButton("🗑️ Excluir")
        self.set_default_btn = QPushButton("⭐ Definir como Padrão")

        self.add_btn.clicked.connect(self.add_connection)
        self.edit_btn.clicked.connect(self.edit_connection)
        self.remove_btn.clicked.connect(self.remove_connection)
        self.set_default_btn.clicked.connect(self.set_default_connection)

        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.edit_btn)
        btn_layout.addWidget(self.remove_btn)
        btn_layout.addWidget(self.set_default_btn)

        layout.addLayout(btn_layout)

        # Botões finais
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("Fechar")
        close_btn.clicked.connect(self.accept)
        close_btn.setMinimumHeight(35)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

    def apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #1a1d21;
            }
            QLabel {
                color: #ffffff;
            }
            QListWidget {
                background-color: #2d3748;
                border: 2px solid #374151;
                border-radius: 8px;
                padding: 8px;
                font-size: 11pt;
                color: #ffffff;
                outline: none;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #374151;
            }
            QListWidget::item:selected {
                background-color: #3b82f6;
                color: white;
                border-radius: 5px;
            }
            QListWidget::item:hover {
                background-color: #374151;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #374151;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 16px;
                border: none;
                min-height: 35px;
            }
            QPushButton:hover {
                background-color: #4b5563;
            }
            QPushButton:disabled {
                background-color: #1f2937;
                color: #6b7280;
            }
            QPushButton:pressed {
                background-color: #1f2937;
            }
        """)

    # =============================
    # CARREGAR CONEXÕES EXISTENTES
    # =============================
    def load_connections(self):
        self.conn_list.clear()

        conexoes = self.db_manager.obter_conexoes()
        default_conn = self.db_manager.obter_conexao_padrao()

        for conn in conexoes:
            item = QListWidgetItem(f"{conn['nome_conexao']}")

            # Guardar dados no item
            item.setData(Qt.UserRole, conn)

            if default_conn and conn["id"] == default_conn["id"]:
                item.setForeground(QColor("#10b981"))
                item.setText(f"{conn['nome_conexao']}  ⭐ (Padrão)")

            self.conn_list.addItem(item)

    # =============================
    # ADICIONAR CONEXÃO
    # =============================
    def add_connection(self):
        name, ok = QInputDialog.getText(self, "Nome da Conexão", "Informe o nome:")
        if not ok or not name.strip():
            return

        conn_str, ok = QInputDialog.getMultiLineText(self, "String de Conexão",
                                                     "DRIVER={ODBC Driver 17 for SQL Server};SERVER=...;DATABASE=...;UID=...;PWD=...")
        if not ok or not conn_str.strip():
            return

        self.db_manager.salvar_conexao_banco(name, conn_str, padrao=False)
        self.load_connections()

    # =============================
    # EDITAR CONEXÃO
    # =============================
    def edit_connection(self):
        item = self.conn_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Selecione", "Escolha uma conexão para editar.")
            return

        conn = item.data(Qt.UserRole)

        name, ok = QInputDialog.getText(self, "Editar Nome", "Novo nome:", text=conn["nome_conexao"])
        if not ok or not name.strip():
            return

        conn_str, ok = QInputDialog.getMultiLineText(self, "Editar String de Conexão",
                                                     "String:", text=conn["string_conexao"])
        if not ok or not conn_str.strip():
            return

        # Para permitir edição, o INSERT OR REPLACE exige chave única
        self.db_manager.salvar_conexao_banco(name, conn_str, padrao=(conn["padrao"] == 1))
        self.load_connections()

    # =============================
    # REMOVER CONEXÃO
    # =============================
    def remove_connection(self):
        item = self.conn_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Selecione", "Escolha uma conexão para excluir.")
            return

        conn = item.data(Qt.UserRole)

        confirm = QMessageBox.question(
            self, "Excluir",
            f"Remover conexão '{conn['nome_conexao']}'?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.No:
            return

        self.db_manager.excluir_conexao(conn["id"])
        self.load_connections()

    # =============================
    # DEFINIR COMO PADRÃO
    # =============================
    def set_default_connection(self):
        item = self.conn_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Selecione", "Escolha uma conexão para definir como padrão.")
            return

        conn = item.data(Qt.UserRole)

        # Atualizar no banco
        self.db_manager.salvar_conexao_banco(conn["nome_conexao"],
                                             conn["string_conexao"],
                                             padrao=True)

        # Recarregar lista com o novo padrão
        self.load_connections()

# =====================
# JANELA PRINCIPAL
# =====================

class ImageCleanerMain(QMainWindow):
    """Janela principal do sistema"""
    
    def __init__(self, db_manager: DatabaseManager, user: Dict):
        super().__init__()
        self.db_manager = db_manager
        self.current_user = user
        
        self.setWindowTitle(f"Image Cleaner ASL - {user['nome_completo']}")
        self.resize(1200, 800)
        
        # Carregar configuracoes
        self.load_configurations()
        
        self.setup_ui()
        self.setStyle()
        
        # Conectar sinais
        emitter.log_signal.connect(self.append_log)
        emitter.progress_signal.connect(self.update_progress)
        emitter.status_signal.connect(self.update_status)
        emitter.enable_clean_signal.connect(self.clean_btn.setEnabled)
        
        # Verificar conexao
        self.check_sql_connection()
    
    def load_configurations(self):
        """Carrega configuracoes do banco"""
        self.image_folder = self.db_manager.obter_config("path_imagens", "C:\\IMAGENS_PRINTER")
        self.sql_connection = self.db_manager.obter_conexao_padrao()
        
        # Estado interno
        self.found_folders = []
        self.db_statistics = {}
    
    def setup_ui(self):
        """Configura interface principal"""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # =============== CABEÇALHO ===============
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #0f172a, stop:1 #1e293b);
                border-radius: 10px;
                padding: 20px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        
        title_layout = QHBoxLayout()
        
        # Ícone e título
        icon_title_layout = QHBoxLayout()
        icon_label = QLabel("🖥️")
        icon_label.setFont(QFont("Segoe UI", 24))
        
        title_container = QVBoxLayout()
        title = QLabel("IMAGE CLEANER ASL")
        title.setFont(QFont("Segoe UI", 20, QFont.Bold))
        title.setStyleSheet("color: #ffffff;")
        
        subtitle = QLabel("Sistema Integrado de Limpeza de Pastas e Banco de Dados")
        subtitle.setFont(QFont("Segoe UI", 10))
        subtitle.setStyleSheet("color: #94a3b8;")
        
        title_container.addWidget(title)
        title_container.addWidget(subtitle)
        
        icon_title_layout.addWidget(icon_label)
        icon_title_layout.addLayout(title_container)
        icon_title_layout.addStretch()
        
        # Informações do usuário
        user_info = QLabel(f"👤 {self.current_user['nome_completo']} ({self.current_user['nivel_acesso'].upper()})")
        user_info.setFont(QFont("Segoe UI", 11))
        user_info.setStyleSheet("""
            color: #cbd5e1; 
            background-color: rgba(255,255,255,0.1); 
            padding: 8px 15px; 
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.1);
        """)
        
        title_layout.addLayout(icon_title_layout)
        title_layout.addWidget(user_info)
        
        header_layout.addLayout(title_layout)
        main_layout.addWidget(header_frame)
        
        # =============== CONFIGURAÇÕES ===============
        config_group = QGroupBox("⚙️ CONFIGURAÇÕES DE LIMPEZA")
        config_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #374151;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #1f2937;
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px 0 10px;
                color: #60a5fa;
            }
        """)
        
        config_layout = QGridLayout()
        config_layout.setSpacing(15)
        
        # Linha 1: Período de limpeza
        period_label = QLabel("📅 Selecione o período que deseja apagar:")
        period_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        period_label.setStyleSheet("color: #d1d5db;")
        config_layout.addWidget(period_label, 0, 0, 1, 2)
        
        # Linha 2: Datas lado a lado
        date_layout = QHBoxLayout()
        date_layout.setSpacing(10)
        
        date_layout.addWidget(QLabel("De:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addMonths(-2))
        self.start_date.setDisplayFormat("dd/MM/yyyy")
        self.start_date.setMinimumHeight(35)
        self.start_date.setStyleSheet("""
            QDateEdit {
                background-color: #374151;
                color: #ffffff;
                border: 2px solid #4b5563;
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 13px;
            }
            QDateEdit:hover {
                border-color: #6b7280;
            }
            QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 25px;
                border-left-width: 1px;
                border-left-color: #4b5563;
                border-left-style: solid;
                border-top-right-radius: 6px;
                border-bottom-right-radius: 6px;
            }
        """)
        date_layout.addWidget(self.start_date)
        
        date_layout.addWidget(QLabel("Até:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat("dd/MM/yyyy")
        self.end_date.setMinimumHeight(35)
        self.end_date.setStyleSheet(self.start_date.styleSheet())
        date_layout.addWidget(self.end_date)
        
        date_layout.addStretch()
        
        config_layout.addLayout(date_layout, 1, 0, 1, 2)
        
        # Linha 3: Períodos rápidos
       
        
        # Linha 4: Caminho das pastas
        folder_layout = QHBoxLayout()
        folder_layout.setSpacing(10)
        
        folder_layout.addWidget(QLabel("📁 Pasta de Imagens:"))
        self.folder_path_input = QLineEdit(self.image_folder)
        self.folder_path_input.setMinimumHeight(35)
        self.folder_path_input.setStyleSheet("""
            QLineEdit {
                background-color: #374151;
                color: #ffffff;
                border: 2px solid #4b5563;
                border-radius: 6px;
                padding: 0 10px;
                font-size: 13px;
                selection-background-color: #3b82f6;
            }
            QLineEdit:hover {
                border-color: #6b7280;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
                background-color: #4b5563;
            }
        """)
        
        browse_btn = QPushButton("📂 Procurar...")
        browse_btn.clicked.connect(self.browse_folder)
        browse_btn.setMinimumHeight(35)
        browse_btn.setMaximumWidth(120)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #4b5563;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #6b7280;
            }
            QPushButton:pressed {
                background-color: #374151;
            }
        """)
        
        folder_layout.addWidget(self.folder_path_input, 1)
        folder_layout.addWidget(browse_btn)
        
        config_layout.addLayout(folder_layout, 3, 0, 1, 2)
        
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)
        
        # =============== CONEXAO SQL SERVER ===============
        sql_group = QGroupBox("🔗 CONEXÃO SQL SERVER")
        sql_group.setStyleSheet(config_group.styleSheet())
        
        sql_layout = QHBoxLayout()
        sql_layout.setSpacing(15)
        
        self.sql_info_label = QLabel("⚠️ Nenhuma conexão configurada")
        self.sql_info_label.setStyleSheet("""
            color: #9ca3af; 
            font-style: italic; 
            padding: 10px;
            background-color: rgba(255,255,255,0.05);
            border-radius: 6px;
            border: 1px dashed #4b5563;
        """)
        
        self.config_sql_btn = QPushButton("⚙️ Configurar")
        self.config_sql_btn.clicked.connect(self.configure_sql_connections)
        self.config_sql_btn.setMinimumHeight(35)
        self.config_sql_btn.setStyleSheet(browse_btn.styleSheet())
        
        self.test_sql_btn = QPushButton("🔌 Testar Conexão")
        self.test_sql_btn.clicked.connect(self.test_current_sql_connection)
        self.test_sql_btn.setMinimumHeight(35)
        self.test_sql_btn.setEnabled(False)
        self.test_sql_btn.setStyleSheet(browse_btn.styleSheet())
        
        sql_layout.addWidget(self.sql_info_label, 1)
        sql_layout.addWidget(self.config_sql_btn)
        sql_layout.addWidget(self.test_sql_btn)
        
        sql_group.setLayout(sql_layout)
        main_layout.addWidget(sql_group)
        
        # =============== AÇÕES PRINCIPAIS ===============
        actions_group = QGroupBox("🚀 AÇÕES DE LIMPEZA")
        actions_group.setStyleSheet(config_group.styleSheet())
        
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(20)
        
        self.analyze_btn = QPushButton("🔍 ANALISAR TUDO")
        self.analyze_btn.clicked.connect(self.on_analyze_all)
        self.analyze_btn.setMinimumHeight(55)
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 15px;
                font-size: 13pt;
                border: none;
            }
            QPushButton:hover { 
                background-color: #2563eb;
                border: 2px solid #1d4ed8;
            }
            QPushButton:pressed { 
                background-color: #1d4ed8;
            }
            QPushButton:disabled { 
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
        
        self.clean_btn = QPushButton("🗑️ EXECUTAR LIMPEZA COMPLETA")
        self.clean_btn.clicked.connect(self.on_clean_all)
        self.clean_btn.setMinimumHeight(55)
        self.clean_btn.setEnabled(False)
        self.clean_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                padding: 15px;
                font-size: 13pt;
                border: none;
            }
            QPushButton:hover { 
                background-color: #dc2626;
                border: 2px solid #b91c1c;
            }
            QPushButton:pressed { 
                background-color: #b91c1c;
            }
            QPushButton:disabled { 
                background-color: #4b5563;
                color: #9ca3af;
            }
        """)
        
        actions_layout.addWidget(self.analyze_btn)
        actions_layout.addWidget(self.clean_btn)
        actions_group.setLayout(actions_layout)
        main_layout.addWidget(actions_group)
        
        # =============== ABA DE RESULTADOS ===============
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #374151;
                border-radius: 8px;
                background-color: #1f2937;
            }
            QTabBar::tab {
                background-color: #374151;
                color: #9ca3af;
                padding: 12px 24px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-weight: bold;
                font-size: 11pt;
                min-width: 180px;
            }
            QTabBar::tab:selected {
                background-color: #3b82f6;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #4b5563;
                color: #d1d5db;
            }
        """)
        
        # Tab 1: Resultados Pastas
        self.folder_tab = QWidget()
        folder_layout = QVBoxLayout(self.folder_tab)
        folder_layout.setContentsMargins(15, 15, 15, 15)
        folder_layout.setSpacing(15)
        
        folder_stats_frame = QFrame()
        folder_stats_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 2px solid #1e293b;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        folder_stats_layout = QHBoxLayout(folder_stats_frame)
        
        self.folder_count_label = QLabel("📁 Pastas encontradas: 0")
        self.folder_count_label.setStyleSheet("font-weight: bold; color: #60a5fa; font-size: 12px;")
        
        self.folder_size_label = QLabel("💾 Espaço total: 0 MB")
        self.folder_size_label.setStyleSheet("font-weight: bold; color: #60a5fa; font-size: 12px;")
        
        folder_stats_layout.addWidget(self.folder_count_label)
        folder_stats_layout.addWidget(self.folder_size_label)
        folder_stats_layout.addStretch()
        
        folder_layout.addWidget(folder_stats_frame)
        
        self.folder_log = QTextEdit()
        self.folder_log.setReadOnly(True)
        self.folder_log.setStyleSheet("""
            QTextEdit {
                background-color: #111827;
                border: 2px solid #374151;
                border-radius: 8px;
                font-family: 'Consolas', 'Monospace', 'Courier New';
                font-size: 10pt;
                padding: 15px;
                color: #d1d5db;
            }
        """)
        folder_layout.addWidget(self.folder_log)
        
        # Tab 2: Resultados Banco
        self.db_tab = QWidget()
        db_layout = QVBoxLayout(self.db_tab)
        db_layout.setContentsMargins(15, 15, 15, 15)
        db_layout.setSpacing(15)
        
        db_stats_frame = QFrame()
        db_stats_frame.setStyleSheet(folder_stats_frame.styleSheet())
        db_stats_layout = QHBoxLayout(db_stats_frame)
        
        self.db_jobs_label = QLabel("📊 Jobs: 0")
        self.db_jobs_label.setStyleSheet("font-weight: bold; color: #10b981; font-size: 12px;")
        
        self.db_details_label = QLabel("📋 Detalhes: 0")
        self.db_details_label.setStyleSheet("font-weight: bold; color: #10b981; font-size: 12px;")
        
        self.db_history_label = QLabel("📜 Histórico: 0")
        self.db_history_label.setStyleSheet("font-weight: bold; color: #10b981; font-size: 12px;")
        
        db_stats_layout.addWidget(self.db_jobs_label)
        db_stats_layout.addWidget(self.db_details_label)
        db_stats_layout.addWidget(self.db_history_label)
        db_stats_layout.addStretch()
        
        db_layout.addWidget(db_stats_frame)
        
        self.db_log = QTextEdit()
        self.db_log.setReadOnly(True)
        self.db_log.setStyleSheet(self.folder_log.styleSheet())
        db_layout.addWidget(self.db_log)
        
        self.tab_widget.addTab(self.folder_tab, "📁 Resultados Pastas")
        self.tab_widget.addTab(self.db_tab, "💾 Resultados Banco")
        
        main_layout.addWidget(self.tab_widget, 1)
        
        # =============== BARRA DE PROGRESSO ===============
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #374151;
                border-radius: 8px;
                text-align: center;
                height: 25px;
                font-weight: bold;
                background-color: #1f2937;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #10b981, stop:1 #3b82f6);
                border-radius: 6px;
            }
        """)
        main_layout.addWidget(self.progress_bar)
        
        # =============== STATUS ===============
        self.status_label = QLabel("✅ Pronto para análise")
        self.status_label.setStyleSheet("""
            font-weight: bold; 
            font-size: 12px; 
            color: #ffffff; 
            background-color: rgba(59, 130, 246, 0.2); 
            padding: 12px 15px; 
            border-radius: 8px; 
            border-left: 4px solid #3b82f6;
            border: 1px solid rgba(59, 130, 246, 0.3);
        """)
        main_layout.addWidget(self.status_label)
        
        # Atualizar informações de conexao
        self.update_sql_info()
    
    def setStyle(self):
        """Aplica estilo a janela"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #111827;
            }
            QLabel {
                font-family: 'Segoe UI', Arial, sans-serif;
                color: #ffffff;
            }
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
    
    def update_period(self, period):
        """Atualiza o periodo baseado na selecao"""
        today = QDate.currentDate()
        if period == "Últimos 30 dias":
            self.start_date.setDate(today.addDays(-30))
        elif period == "Últimos 60 dias":
            self.start_date.setDate(today.addDays(-60))
        elif period == "Últimos 90 dias":
            self.start_date.setDate(today.addDays(-90))
        elif period == "Últimos 6 meses":
            self.start_date.setDate(today.addMonths(-6))
        elif period == "Último ano":
            self.start_date.setDate(today.addYears(-1))
        self.end_date.setDate(today)
    
    def browse_folder(self):
        """Seleciona pasta de imagens"""
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Imagens")
        if folder:
            self.folder_path_input.setText(folder)
            self.db_manager.salvar_config("path_imagens", folder, "Caminho das pastas de imagens")
    
    def update_sql_info(self):
        """Atualiza informações da conexao SQL"""
        if self.sql_connection:
            info = f"🔗 {self.sql_connection['nome_conexao']} - {self.sql_connection['string_conexao'][:50]}..."
            self.sql_info_label.setText(info)
            self.test_sql_btn.setEnabled(True)
            self.sql_info_label.setStyleSheet("""
                color: #10b981; 
                font-weight: bold; 
                padding: 10px;
                background-color: rgba(16, 185, 129, 0.1);
                border-radius: 6px;
                border: 1px solid rgba(16, 185, 129, 0.3);
            """)
        else:
            self.sql_info_label.setText("⚠️ Nenhuma conexão SQL Server configurada")
            self.test_sql_btn.setEnabled(False)
            self.sql_info_label.setStyleSheet("""
                color: #f59e0b; 
                font-style: italic; 
                padding: 10px;
                background-color: rgba(245, 158, 11, 0.1);
                border-radius: 6px;
                border: 1px dashed rgba(245, 158, 11, 0.3);
            """)
    
    def check_sql_connection(self):
        """Verifica conexao com SQL Server em segundo plano"""
        if self.sql_connection:
            def check():
                conn_str = self.sql_connection['string_conexao']
                if test_database_connection(conn_str):
                    emitter.status_signal.emit("✅ Conexão SQL Server verificada com sucesso")
                else:
                    emitter.status_signal.emit("❌ Falha na conexão SQL Server")
            
            threading.Thread(target=check, daemon=True).start()
    
    def append_log(self, message: str, level: str = "INFO", database: bool = False):
        """Adiciona mensagem ao log"""
        log_widget = self.db_log if database else self.folder_log
        
        # Definir cor
        if level == "ERROR":
            color = "#ef4444"
            prefix = "❌ "
        elif level == "WARNING":
            color = "#f59e0b"
            prefix = "⚠️ "
        elif level == "SUCCESS":
            color = "#10b981"
            prefix = "✅ "
        elif level == "DB_INFO" or level == "DB_SUCCESS":
            color = "#3b82f6"
            prefix = "💾 "
        else:
            color = "#d1d5db"
            prefix = "ℹ️ "
        
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f'<span style="color:#9ca3af;">[{timestamp}]</span> <span style="color:{color};font-weight:bold;">{prefix}{message}</span>'
        
        log_widget.append(formatted)
        
        # Scroll para o final
        cursor = log_widget.textCursor()
        cursor.movePosition(QTextCursor.End)
        log_widget.setTextCursor(cursor)
    
    def update_progress(self, value):
        """Atualiza barra de progresso"""
        self.progress_bar.setValue(value)
    
    def update_status(self, message):
        """Atualiza mensagem de status"""
        self.status_label.setText(message)
    
    def on_analyze_all(self):
        """Analisa pastas e banco"""
        start_date = self.start_date.date().toPython()
        end_date = self.end_date.date().toPython()
        folder_path = self.folder_path_input.text()
        
        # Validacoes
        if start_date > end_date:
            QMessageBox.warning(self, "Data inválida", "A data inicial não pode ser maior que a final.")
            return
        
        if not os.path.exists(folder_path):
            QMessageBox.warning(self, "Pasta não encontrada", f"A pasta não existe:\n{folder_path}")
            return
        
        if not self.sql_connection:
            QMessageBox.warning(self, "Conexão não configurada", "Configure uma conexão SQL Server primeiro.")
            return
        
        # Limpar logs anteriores
        self.folder_log.clear()
        self.db_log.clear()
        
        # Configurar interface
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.analyze_btn.setEnabled(False)
        self.clean_btn.setEnabled(False)
        
        # Limpar dados anteriores
        self.found_folders = []
        self.db_statistics = {}
        
        # Atualizar status
        emitter.status_signal.emit("🔍 Analisando pastas e banco de dados...")
        
        def analyze_thread():
            try:
                # Analise de pastas
                emitter.log_signal.emit("=== ANÁLISE DE PASTAS ===", "INFO", False)
                
                # Registrar log de atividade
                self.db_manager.registrar_log(
                    self.current_user['id'], 
                    "INICIO_ANALISE_PASTAS", 
                    "Limpeza",
                    f"Período: {start_date} a {end_date}"
                )
                
                folders = get_folder_statistics(folder_path, start_date, end_date)
                self.found_folders = folders
                
                # Atualizar estatisticas
                total_folders = len(folders)
                total_size = sum([f['Size'] for f in folders])
                
                self.folder_count_label.setText(f"📁 Pastas encontradas: {total_folders}")
                self.folder_size_label.setText(f"💾 Espaço total: {total_size:.2f} MB")
                
                if total_folders > 0:
                    emitter.log_signal.emit(f"Encontradas {total_folders} pastas ({total_size:.2f} MB)", "SUCCESS", False)
                    # Registrar sucesso no log
                    self.db_manager.registrar_log(
                        self.current_user['id'],
                        "SUCESSO_ANALISE_PASTAS",
                        "Limpeza",
                        f"Encontradas {total_folders} pastas ({total_size:.2f} MB)"
                    )
                else:
                    emitter.log_signal.emit("Nenhuma pasta encontrada no período", "INFO", False)
                
                # Analise do banco
                emitter.log_signal.emit("=== ANÁLISE DO BANCO DE DADOS ===", "INFO", True)
                
                # Obter string de conexao
                conn_str = self.sql_connection['string_conexao']
                
                db_start = datetime.combine(start_date, datetime.min.time())
                db_end = datetime.combine(end_date, datetime.max.time())
                
                db_stats = get_database_statistics(conn_str, db_start, db_end)
                self.db_statistics = db_stats if db_stats else {}
                
                if db_stats:
                    jobs = db_stats.get('JobsCount', 0)
                    details = db_stats.get('DetailsCount', 0)
                    history = db_stats.get('HistoryCount', 0)
                    total_records = jobs + details + history
                    
                    self.db_jobs_label.setText(f"📊 Jobs: {jobs}")
                    self.db_details_label.setText(f"📋 Detalhes: {details}")
                    self.db_history_label.setText(f"📜 Histórico: {history}")
                    
                    if total_records > 0:
                        emitter.log_signal.emit(f"Encontrados {total_records} registros no banco", "DB_SUCCESS", True)
                        self.db_manager.registrar_log(
                            self.current_user['id'],
                            "SUCESSO_ANALISE_BANCO",
                            "Limpeza",
                            f"Encontrados {total_records} registros"
                        )
                    else:
                        emitter.log_signal.emit("Nenhum registro encontrado no período", "INFO", True)
                else:
                    emitter.log_signal.emit("Não foi possível acessar o banco de dados", "WARNING", True)
                
                # Verificar se ha algo para limpar
                has_data_to_clean = (total_folders > 0) or (self.db_statistics and sum(self.db_statistics.values()) > 0)
                
                if has_data_to_clean:
                    emitter.enable_clean_signal.emit(True)
                    emitter.status_signal.emit("✅ Análise concluída - Pronto para limpeza")
                else:
                    emitter.status_signal.emit("ℹ️ Análise concluída - Nada para limpar")
                
                # Registrar conclusao da analise
                self.db_manager.registrar_log(
                    self.current_user['id'],
                    "CONCLUSAO_ANALISE",
                    "Limpeza",
                    f"Pastas: {total_folders}, Registros: {self.db_statistics.get('JobsCount', 0) if self.db_statistics else 0}"
                )
                
            except Exception as e:
                emitter.log_signal.emit(f"Erro durante a análise: {str(e)}", "ERROR", False)
                emitter.status_signal.emit("❌ Erro na análise")
                # Registrar erro no log
                self.db_manager.registrar_log(
                    self.current_user['id'],
                    "ERRO_ANALISE",
                    "Limpeza",
                    f"Erro: {str(e)}"
                )
            finally:
                self.analyze_btn.setEnabled(True)
                self.progress_bar.setVisible(False)
        
        threading.Thread(target=analyze_thread, daemon=True).start()
    
    def on_clean_all(self):
        """Executa limpeza completa"""
        if not self.found_folders and not self.db_statistics:
            QMessageBox.information(self, "Nada para limpar", "Não há dados para limpar.")
            return
        
        # Mensagem de confirmacao
        message = "⚠️ CONFIRMAR LIMPEZA COMPLETA ⚠️\n\n"
        
        if self.found_folders:
            total_folders = len(self.found_folders)
            total_size = sum([f['Size'] for f in self.found_folders])
            message += f"📁 Pastas: {total_folders} ({total_size:.2f} MB)\n"
        
        if self.db_statistics:
            jobs = self.db_statistics.get('JobsCount', 0)
            details = self.db_statistics.get('DetailsCount', 0)
            history = self.db_statistics.get('HistoryCount', 0)
            if jobs + details + history > 0:
                message += f"💾 Registros do banco: {jobs + details + history}\n"
        
        message += "\n🚨 ESTA AÇÃO NÃO PODE SER DESFEITA!\nDeseja continuar?"
        
        reply = QMessageBox.question(self, 'Confirmação', message,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.No:
            return
        
        # Executar limpeza
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.clean_btn.setEnabled(False)
        self.analyze_btn.setEnabled(False)
        
        def cleanup_thread():
            try:
                emitter.status_signal.emit("🚀 Executando limpeza...")
                
                deleted_folders = 0
                deleted_db_records = 0
                
                # Limpar pastas
                if self.found_folders:
                    emitter.log_signal.emit("=== LIMPEZA DE PASTAS ===", "INFO", False)
                    deleted_folders, errors = delete_folders(
                        self.found_folders, self.db_manager, self.current_user['id']
                    )
                    emitter.log_signal.emit(f"Pastas excluídas: {deleted_folders}, Erros: {errors}", "SUCCESS", False)
                
                # Limpar banco
                if self.db_statistics and sum(self.db_statistics.values()) > 0:
                    emitter.log_signal.emit("=== LIMPEZA DO BANCO ===", "INFO", True)
                    start_date = self.start_date.date().toPython()
                    end_date = self.end_date.date().toPython()
                    db_start = datetime.combine(start_date, datetime.min.time())
                    db_end = datetime.combine(end_date, datetime.max.time())
                    
                    # Connection string
                    conn_str = self.sql_connection['string_conexao']
                    
                    result = execute_database_cleanup(
                        conn_str, db_start, db_end, 
                        self.db_manager, self.current_user['id']
                    )
                    
                    if result.get('Success'):
                        deleted_db_records = result.get('JobsDeleted', 0) + result.get('DetailsDeleted', 0) + result.get('HistoryDeleted', 0)
                        emitter.log_signal.emit(f"Registros excluídos: {deleted_db_records}", "DB_SUCCESS", True)
                    else:
                        emitter.log_signal.emit("Falha na limpeza do banco", "ERROR", True)
                
                # Resumo final
                summary = f"✅ LIMPEZA CONCLUÍDA\n\n"
                if deleted_folders > 0:
                    summary += f"📁 Pastas excluídas: {deleted_folders}\n"
                if deleted_db_records > 0:
                    summary += f"💾 Registros excluídos: {deleted_db_records}\n"
                
                emitter.status_signal.emit(summary.strip())
                
                # Log de atividade
                self.db_manager.registrar_log(
                    self.current_user['id'], "LIMPEZA_CONCLUIDA", "Limpeza",
                    f"Pastas: {deleted_folders}, Registros: {deleted_db_records}"
                )
                
                # Limpar dados
                self.found_folders = []
                self.db_statistics = {}
                
                # Atualizar estatisticas
                self.folder_count_label.setText("📁 Pastas encontradas: 0")
                self.folder_size_label.setText("💾 Espaço total: 0 MB")
                self.db_jobs_label.setText("📊 Jobs: 0")
                self.db_details_label.setText("📋 Detalhes: 0")
                self.db_history_label.setText("📜 Histórico: 0")
                
            except Exception as e:
                emitter.log_signal.emit(f"Erro durante a limpeza: {str(e)}", "ERROR", False)
                emitter.status_signal.emit("❌ Erro na limpeza")
            finally:
                self.analyze_btn.setEnabled(True)
                self.progress_bar.setVisible(False)
        
        threading.Thread(target=cleanup_thread, daemon=True).start()
    
    # =============== MÉTODOS DO MENU ===============
    
    def configure_sql_connections(self):
        """Abre dialogo para gerenciar conexoes SQL Server"""
        dialog = ConfigSQLDialog(self.db_manager)
        if dialog.exec():
            # Atualizar conexao padrao
            self.sql_connection = self.db_manager.obter_conexao_padrao()
            self.update_sql_info()
            
            # Registrar log
            self.db_manager.registrar_log(
                self.current_user['id'],
                "GERENCIAR_CONEXOES",
                "Sistema",
                "Configurações de conexão atualizadas"
            )
    
    def test_current_sql_connection(self):
        """Testa a conexao SQL atual"""
        if not self.sql_connection:
            QMessageBox.warning(self, "Sem conexão", "Nenhuma conexão SQL configurada.")
            return
        
        conn_str = self.sql_connection['string_conexao']
        
        if test_database_connection(conn_str):
            QMessageBox.information(self, "Teste de Conexão", "✅ Conexão bem-sucedida!")
        else:
            QMessageBox.critical(self, "Teste de Conexão", "❌ Falha na conexão.")
    
    def show_about(self):
        """Mostra informações sobre o sistema"""
        QMessageBox.about(self, "Sobre",
                         "Image Cleaner ASL - Enterprise Edition v3.2\n\n"
                         "Sistema completo para limpeza de pastas de imagens\n"
                         "e registros do banco de dados SQL Server.\n\n"
                         f"Diretório: {get_app_directory()}\n"
                         f"Logs: {get_logs_directory()}\n\n"
                         "© 2024 - Todos os direitos reservados")
    
    def logout(self):
        """Faz logout do sistema"""
        reply = QMessageBox.question(self, "Sair", "Deseja realmente sair do sistema?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.db_manager.registrar_log(
                self.current_user['id'], "LOGOUT", "Sistema",
                f"Usuário {self.current_user['login']} fez logout"
            )
            self.close()

# =====================
# SCRIPT PARA RESETAR O BANCO
# =====================

def resetar_banco():
    """Função para resetar o banco de dados manualmente"""
    app_dir = get_app_directory()
    db_path = os.path.join(app_dir, "Cleaner.db3")
    
    print("=" * 60)
    print("RESETANDO BANCO DE DADOS")
    print("=" * 60)
    
    # Verificar se o arquivo existe
    if os.path.exists(db_path):
        print(f"Arquivo atual: {db_path}")
        print(f"Tamanho: {os.path.getsize(db_path)} bytes")
        
        # Fazer backup
        backup_path = db_path + ".backup"
        try:
            shutil.copy2(db_path, backup_path)
            print(f"Backup criado: {backup_path}")
        except Exception as e:
            print(f"Erro ao criar backup: {e}")
        
        # Remover arquivo
        try:
            os.remove(db_path)
            print("Arquivo removido com sucesso")
        except Exception as e:
            print(f"Erro ao remover arquivo: {e}")
            return
    else:
        print(f"Arquivo não existe: {db_path}")
    
    # Criar novo banco
    try:
        # Garantir que o diretório existe
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Criar tabela de usuários
        cursor.execute('''
            CREATE TABLE usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL,
                nome_completo TEXT,
                nivel_acesso TEXT DEFAULT 'operador' CHECK (nivel_acesso IN ('operador', 'supervisor', 'administrador')),
                ativo INTEGER DEFAULT 1,
                data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                ultimo_login DATETIME
            )
        ''')
        
        # Criar usuário admin
        cursor.execute('''
            INSERT INTO usuarios (login, senha, nome_completo, nivel_acesso)
            VALUES (?, ?, ?, ?)
        ''', ('admin', '123', 'Administrador do Sistema', 'administrador'))
        
        conn.commit()
        
        # Verificar
        cursor.execute("SELECT * FROM usuarios")
        users = cursor.fetchall()
        print(f"\nUsuários criados: {len(users)}")
        for user in users:
            print(f"  ID: {user[0]}, Login: '{user[1]}', Senha: '{user[2]}', Nome: '{user[3]}', Nível: {user[4]}")
        
        conn.close()
        
        print(f"\nBanco de dados resetado com sucesso!")
        print(f"Local: {db_path}")
        print("\nCredenciais:")
        print("  Login: admin")
        print("  Senha: 123")
        print("=" * 60)
        
    except Exception as e:
        print(f"Erro ao criar banco: {e}")
        traceback.print_exc()

# =====================
# FUNÇÃO PRINCIPAL
# =====================

def main():
    """Funcao principal"""
    try:
        app = QApplication(sys.argv)
        
        # Mostrar informacoes do diretorio
        app_dir = get_app_directory()
        print("=" * 60)
        print(f"Diretório do aplicativo: {app_dir}")
        print(f"Banco de dados: {os.path.join(app_dir, 'Cleaner.db3')}")
        print(f"Logs: {get_logs_directory()}")
        print("=" * 60)
        
        # Verificar se o arquivo do banco existe
        db_path = os.path.join(app_dir, 'Cleaner.db3')
        if os.path.exists(db_path):
            print(f"Arquivo do banco EXISTE: {db_path}")
            print(f"Tamanho: {os.path.getsize(db_path)} bytes")
            
            # Tentar ler usuários do banco
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT login, senha, nome_completo, ativo FROM usuarios")
                users = cursor.fetchall()
                print("Usuários no banco:")
                for user in users:
                    print(f"  Login: '{user[0]}', Senha: '{user[1]}', Nome: '{user[2]}', Ativo: {user[3]}")
                conn.close()
            except Exception as e:
                print(f"Erro ao ler banco: {e}")
        else:
            print(f"Arquivo do banco NÃO EXISTE: {db_path}")
            print("Será criado automaticamente...")
        
        # Estilo da aplicacao
        app.setStyle("Fusion")
        
        # Estilo global para melhor responsividade
        app.setStyleSheet("""
            * {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QMainWindow, QDialog {
                background-color: #111827;
            }
            QMessageBox {
                background-color: #1f2937;
                color: #ffffff;
            }
            QMessageBox QLabel {
                color: #ffffff;
            }
            QMessageBox QPushButton {
                background-color: #374151;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                min-height: 30px;
            }
            QMessageBox QPushButton:hover {
                background-color: #4b5563;
            }
        """)
        
        # Inicializar banco de dados SQLite
        write_log("Inicializando banco de dados SQLite...", "INFO")
        db_manager = DatabaseManager()
        
        # Mostrar tela de login
        login_dialog = LoginDialog(db_manager)
        
        # Criar variável para armazenar o usuário autenticado
        authenticated_user = None
        
        # Conectar sinal de login ANTES de executar o diálogo
        def on_login_success(user_data):
            nonlocal authenticated_user
            authenticated_user = user_data
        
        login_dialog.login_success.connect(on_login_success)
        
        # Executar diálogo de login
        if login_dialog.exec() == QDialog.Accepted and authenticated_user:
            # Mostrar janela principal
            window = ImageCleanerMain(db_manager, authenticated_user)
            window.show()
            
            # Registrar inicio da aplicacao
            db_manager.registrar_log(
                authenticated_user['id'], 
                "INICIO_APLICACAO", 
                "Sistema", 
                f"Aplicação iniciada em {app_dir}"
            )
            
            sys.exit(app.exec())
        else:
            print("Login cancelado ou falhou.")
            print("\nSe o login continuar falhando, tente:")
            print("1. Execute como administrador")
            print("2. Use a função resetar_banco() abaixo")
            print("3. Verifique se há permissão de escrita na pasta")
            
            # Perguntar se quer resetar o banco
            resposta = input("\nDeseja resetar o banco de dados? (s/n): ")
            if resposta.lower() == 's':
                resetar_banco()
                print("\nTente executar o programa novamente.")
            
            sys.exit(0)
        
    except Exception as e:
        print(f"Erro fatal: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    # Verificar se o usuário quer resetar o banco via linha de comando
    if len(sys.argv) > 1 and sys.argv[1] == "--reset-db":
        resetar_banco()
    else:
        main()