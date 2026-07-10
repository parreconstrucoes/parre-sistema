from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3, hashlib, jwt, os, datetime, json

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)
SECRET = 'parre_secret_2026'
DB_PATH = os.environ.get('DB_PATH', 'db/parre.db')

def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    # Usuários
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL
    )''')
    # Inserir usuário padrão
    senha_hash = hashlib.sha256('@Agv050794.'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO usuarios (usuario, senha) VALUES (?, ?)",
              ('Parre.Construtora', senha_hash))

    # Obras
    c.execute('''CREATE TABLE IF NOT EXISTS obras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        condominio TEXT,
        rua TEXT,
        quadra TEXT,
        lote TEXT,
        cno TEXT,
        budget REAL DEFAULT 0,
        valor_terreno REAL DEFAULT 0,
        valor_venda REAL DEFAULT 0,
        com_corretor INTEGER DEFAULT 0,
        valor_corretor REAL DEFAULT 0,
        imposto_venda REAL DEFAULT 0,
        status TEXT DEFAULT 'Em andamento',
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # Inserir obra atual
    c.execute("INSERT OR IGNORE INTO obras (id, nome, condominio, rua, quadra, lote, budget, valor_terreno, valor_venda, status) VALUES (1, 'Horto Florestal Villagio', 'Horto Florestal Villagio', 'Rua Alice Manrique Gabriel', 'A4', '09', 600000, 180000, 780000, 'Em andamento')")

    # Mão de obra
    c.execute('''CREATE TABLE IF NOT EXISTS mao_obra (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        obra_id INTEGER NOT NULL,
        descricao TEXT NOT NULL,
        quantidade REAL DEFAULT 1,
        valor_unit REAL DEFAULT 0,
        total REAL GENERATED ALWAYS AS (quantidade * valor_unit) STORED,
        etapa TEXT,
        status TEXT DEFAULT 'Pago',
        data TEXT,
        observacao TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (obra_id) REFERENCES obras(id)
    )''')

    # Serviços da obra
    c.execute('''CREATE TABLE IF NOT EXISTS servicos_obra (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        obra_id INTEGER NOT NULL,
        descricao TEXT NOT NULL,
        quantidade REAL DEFAULT 1,
        valor_unit REAL DEFAULT 0,
        total REAL GENERATED ALWAYS AS (quantidade * valor_unit) STORED,
        etapa TEXT,
        status TEXT,
        data TEXT,
        observacao TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (obra_id) REFERENCES obras(id)
    )''')

    # Materiais
    c.execute('''CREATE TABLE IF NOT EXISTS materiais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        obra_id INTEGER NOT NULL,
        categoria TEXT NOT NULL,
        descricao TEXT NOT NULL,
        quantidade REAL DEFAULT 1,
        valor_unit REAL DEFAULT 0,
        total REAL GENERATED ALWAYS AS (quantidade * valor_unit) STORED,
        etapa TEXT,
        status TEXT,
        data TEXT,
        observacao TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (obra_id) REFERENCES obras(id)
    )''')

    # Custos fixos da obra
    c.execute('''CREATE TABLE IF NOT EXISTS custos_fixos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        obra_id INTEGER NOT NULL,
        tipo TEXT NOT NULL,
        mes_ano TEXT,
        valor REAL DEFAULT 0,
        comprovante TEXT,
        observacao TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (obra_id) REFERENCES obras(id)
    )''')

    # Clientes
    c.execute('''CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        cnpj_cpf TEXT,
        contato TEXT,
        email TEXT,
        observacao TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute("INSERT OR IGNORE INTO clientes (id, nome, cnpj_cpf) VALUES (1, 'Wessel – WEW Importação e Exportação Ltda.', '61.559.589/0002-38')")

    # Orçamentos / Propostas
    c.execute('''CREATE TABLE IF NOT EXISTS orcamentos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER NOT NULL,
        numero_proposta TEXT NOT NULL,
        descricao TEXT NOT NULL,
        valor REAL DEFAULT 0,
        status TEXT DEFAULT 'Aprovado',
        numero_nf TEXT,
        link_pdf TEXT,
        data_aprovacao TEXT,
        data_execucao TEXT,
        data_recebimento TEXT,
        observacao TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (cliente_id) REFERENCES clientes(id)
    )''')

    # Despesas operacionais (prestação)
    c.execute('''CREATE TABLE IF NOT EXISTS despesas_prestacao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cliente_id INTEGER,
        tipo TEXT NOT NULL,
        descricao TEXT NOT NULL,
        valor REAL DEFAULT 0,
        data TEXT,
        status TEXT DEFAULT 'Lançado',
        observacao TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # Folha de pagamento
    c.execute('''CREATE TABLE IF NOT EXISTS folha_pagamento (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        colaborador TEXT NOT NULL,
        funcao TEXT DEFAULT 'Sócio Administrador',
        mes_ano TEXT NOT NULL,
        pro_labore REAL DEFAULT 0,
        inss_percentual REAL DEFAULT 11,
        inss_valor REAL DEFAULT 0,
        liquido REAL DEFAULT 0,
        observacao TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    # DARF / GPS
    c.execute('''CREATE TABLE IF NOT EXISTS darfs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mes_ano TEXT NOT NULL,
        numero_documento TEXT,
        vencimento TEXT,
        codigo_1099 REAL DEFAULT 0,
        codigo_1138 REAL DEFAULT 0,
        total REAL DEFAULT 0,
        pago INTEGER DEFAULT 0,
        data_pagamento TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()
    conn.close()

def _importar_dados_obra(c):
    mao_obra_data = [
        (1,'Pedreiro',1,5000,'Pago'),(1,'Pedreiro',1,5600,'Pago'),(1,'Pedreiro',1,5600,'Pago'),
        (1,'Pedreiro',1,5600,'Pago'),(1,'Pedreiro',1,7100,'Pago'),(1,'Pedreiro',1,5600,'Pago'),
        (1,'Pedreiro',1,1000,'Pago'),(1,'Pedreiro',1,4600,'Pago'),(1,'Pedreiro',1,400,'Pago'),
        (1,'Pedreiro',1,5200,'Pago'),(1,'Pedreiro',1,5600,'Pago'),(1,'Pedreiro',1,5600,'Pago'),
        (1,'Pedreiro',1,5600,'Pago'),(1,'Pedreiro',1,5600,'Pago'),(1,'Pedreiro',1,4300,'Pago'),
        (1,'Pedreiro',1,5600,'Pago'),(1,'Pedreiro',1,5600,'Pago'),(1,'Pedreiro',1,4200,'Pago'),
    ]
    for row in mao_obra_data:
        c.execute("INSERT OR IGNORE INTO mao_obra (obra_id,descricao,quantidade,valor_unit,status) VALUES (?,?,?,?,?)", row)

    servicos_data = [
        (1,'Perfuração de solo',1,1600),(1,'Aluguel de equipamentos',1,1060),(1,'Limpeza do terreno',1,900),
        (1,'Concretagem da fundação (Brocas)',1,2430),(1,'Concretagem (meio metro)',1,202.5),
        (1,'Concretagem da fundação (Baldrame)',1,6075),(1,'Bomba',1,2800),(1,'Reforma',1,11000),
        (1,'SAAE',1,824.14),(1,'Impermeabilização (Fundação)',1,2310.53),(1,'Paulo Eng',1,600),
        (1,'Concretagem Laje 1',1,4565),(1,'Aluguel de equipamentos (banheiro)',2,450),
        (1,'Bomba',1,1200),(1,'Aluguel Vibrador laje',2,75),(1,'Impermeabilização',1,315),
        (1,'Impermeabilização',2,230),(1,'Impermeabilização',1,460),(1,'Concretagem laje 2',1,3320),
        (1,'Esquadria',1,20500),(1,'Ari contabilidade',2,950),(1,'Eletricista',1,12000),
        (1,'Calhas',1,7240),(1,'Gesso',1,8543.20),(1,'Energia Solar 1/2',1,7419.21),
        (1,'Marmoraria',1,15888),(1,'Piscina Clayton',1,7206.40),(1,'Pintura',1,13500),
        (1,'Concretagem garagem e piscina',1,1770),(1,'Portas Disparuet',1,8200),
        (1,'Calhas garagem',1,2290),(1,'Impermeabilização piscina',1,770),
    ]
    for row in servicos_data:
        c.execute("INSERT OR IGNORE INTO servicos_obra (obra_id,descricao,quantidade,valor_unit) VALUES (?,?,?,?)", row)

def token_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Token ausente'}), 401
        try:
            jwt.decode(token, SECRET, algorithms=['HS256'])
        except:
            return jsonify({'error': 'Token inválido'}), 401
        return f(*args, **kwargs)
    return decorated

def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows]

# ============ AUTH ============
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    senha_hash = hashlib.sha256(data.get('senha','').encode()).hexdigest()
    conn = get_db()
    user = conn.execute("SELECT * FROM usuarios WHERE usuario=? AND senha=?",
                        (data.get('usuario',''), senha_hash)).fetchone()
    conn.close()
    if not user:
        return jsonify({'error': 'Usuário ou senha incorretos'}), 401
    token = jwt.encode({'usuario': data['usuario'],
                        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=30)},
                       SECRET, algorithm='HS256')
    return jsonify({'token': token, 'usuario': data['usuario']})

# ============ OBRAS ============
@app.route('/api/obras', methods=['GET'])
@token_required
def get_obras():
    conn = get_db()
    obras = rows_to_list(conn.execute("SELECT * FROM obras ORDER BY criado_em DESC").fetchall())
    for o in obras:
        o['total_mao_obra'] = conn.execute("SELECT COALESCE(SUM(total),0) FROM mao_obra WHERE obra_id=?", (o['id'],)).fetchone()[0]
        o['total_servicos'] = conn.execute("SELECT COALESCE(SUM(total),0) FROM servicos_obra WHERE obra_id=?", (o['id'],)).fetchone()[0]
        o['total_materiais'] = conn.execute("SELECT COALESCE(SUM(total),0) FROM materiais WHERE obra_id=?", (o['id'],)).fetchone()[0]
        o['total_custos_fixos'] = conn.execute("SELECT COALESCE(SUM(valor),0) FROM custos_fixos WHERE obra_id=?", (o['id'],)).fetchone()[0]
        o['total_gasto'] = o['total_mao_obra'] + o['total_servicos'] + o['total_materiais'] + o['total_custos_fixos']
        o['budget_restante'] = o['budget'] - o['total_gasto'] - (o['valor_terreno'] or 0)
    conn.close()
    return jsonify(obras)

@app.route('/api/obras', methods=['POST'])
@token_required
def create_obra():
    d = request.json
    conn = get_db()
    cur = conn.execute("""INSERT INTO obras (nome,condominio,rua,quadra,lote,cno,budget,valor_terreno,valor_venda,com_corretor,valor_corretor,imposto_venda,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d['nome'],d.get('condominio',''),d.get('rua',''),d.get('quadra',''),d.get('lote',''),
         d.get('cno',''),d.get('budget',0),d.get('valor_terreno',0),d.get('valor_venda',0),
         d.get('com_corretor',0),d.get('valor_corretor',0),d.get('imposto_venda',0),'Em andamento'))
    conn.commit()
    obra = row_to_dict(conn.execute("SELECT * FROM obras WHERE id=?", (cur.lastrowid,)).fetchone())
    conn.close()
    return jsonify(obra), 201

@app.route('/api/obras/<int:id>', methods=['PUT'])
@token_required
def update_obra(id):
    d = request.json
    conn = get_db()
    conn.execute("""UPDATE obras SET nome=?,condominio=?,rua=?,quadra=?,lote=?,cno=?,budget=?,
        valor_terreno=?,valor_venda=?,com_corretor=?,valor_corretor=?,imposto_venda=?,status=? WHERE id=?""",
        (d['nome'],d.get('condominio',''),d.get('rua',''),d.get('quadra',''),d.get('lote',''),
         d.get('cno',''),d.get('budget',0),d.get('valor_terreno',0),d.get('valor_venda',0),
         d.get('com_corretor',0),d.get('valor_corretor',0),d.get('imposto_venda',0),d.get('status','Em andamento'),id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/obras/<int:id>', methods=['DELETE'])
@token_required
def delete_obra(id):
    conn = get_db()
    conn.execute("DELETE FROM obras WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

# ============ ROTAS GENÉRICAS CRUD ============
def make_crud(table, fields, obra_fk=True):
    @app.route(f'/api/{table}', methods=['GET'], endpoint=f'get_{table}')
    @token_required
    def get_all():
        obra_id = request.args.get('obra_id')
        conn = get_db()
        if obra_id and obra_fk:
            rows = rows_to_list(conn.execute(f"SELECT * FROM {table} WHERE obra_id=? ORDER BY id DESC", (obra_id,)).fetchall())
        else:
            rows = rows_to_list(conn.execute(f"SELECT * FROM {table} ORDER BY id DESC").fetchall())
        conn.close()
        return jsonify(rows)

    @app.route(f'/api/{table}', methods=['POST'], endpoint=f'post_{table}')
    @token_required
    def create():
        d = request.json
        cols = [f for f in fields if f in d or f.endswith('_id')]
        vals = [d.get(f) for f in cols]
        placeholders = ','.join(['?']*len(cols))
        conn = get_db()
        cur = conn.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})", vals)
        conn.commit()
        row = row_to_dict(conn.execute(f"SELECT * FROM {table} WHERE id=?", (cur.lastrowid,)).fetchone())
        conn.close()
        return jsonify(row), 201

    @app.route(f'/api/{table}/<int:id>', methods=['PUT'], endpoint=f'put_{table}')
    @token_required
    def update(id):
        d = request.json
        sets = ','.join([f"{f}=?" for f in fields if f in d])
        vals = [d[f] for f in fields if f in d] + [id]
        conn = get_db()
        conn.execute(f"UPDATE {table} SET {sets} WHERE id=?", vals)
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

    @app.route(f'/api/{table}/<int:id>', methods=['DELETE'], endpoint=f'del_{table}')
    @token_required
    def delete(id):
        conn = get_db()
        conn.execute(f"DELETE FROM {table} WHERE id=?", (id,))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})

make_crud('mao_obra', ['obra_id','descricao','quantidade','valor_unit','etapa','status','data','observacao'])
make_crud('servicos_obra', ['obra_id','descricao','quantidade','valor_unit','etapa','status','data','observacao'])
make_crud('materiais', ['obra_id','categoria','descricao','quantidade','valor_unit','etapa','status','data','observacao'])
make_crud('custos_fixos', ['obra_id','tipo','mes_ano','valor','comprovante','observacao'])
make_crud('orcamentos', ['cliente_id','numero_proposta','descricao','valor','status','numero_nf','link_pdf','data_aprovacao','data_execucao','data_recebimento','observacao'], obra_fk=False)
make_crud('despesas_prestacao', ['cliente_id','tipo','descricao','valor','data','status','observacao'], obra_fk=False)
make_crud('folha_pagamento', ['colaborador','funcao','mes_ano','pro_labore','inss_percentual','inss_valor','liquido','observacao'], obra_fk=False)
make_crud('darfs', ['mes_ano','numero_documento','vencimento','codigo_1099','codigo_1138','total','pago','data_pagamento'], obra_fk=False)
make_crud('clientes', ['nome','cnpj_cpf','contato','email','observacao'], obra_fk=False)

# ============ RESUMO FINANCEIRO PRESTAÇÃO ============
@app.route('/api/resumo-prestacao', methods=['GET'])
@token_required
def resumo_prestacao():
    mes = request.args.get('mes_ano')
    conn = get_db()
    q_orc = "SELECT COALESCE(SUM(valor),0) FROM orcamentos WHERE status='Recebido'"
    q_desp = "SELECT COALESCE(SUM(valor),0) FROM despesas_prestacao"
    q_folha = "SELECT COALESCE(SUM(pro_labore),0), COALESCE(SUM(inss_valor),0), COALESCE(SUM(liquido),0) FROM folha_pagamento"
    if mes:
        q_orc += " AND data_recebimento LIKE ?"
        q_desp += " WHERE data LIKE ?"
        q_folha += " WHERE mes_ano=?"
        faturamento = conn.execute(q_orc, (f'%{mes}%',)).fetchone()[0]
        despesas = conn.execute(q_desp, (f'%{mes}%',)).fetchone()[0]
        folha = conn.execute(q_folha, (mes,)).fetchone()
    else:
        faturamento = conn.execute(q_orc).fetchone()[0]
        despesas = conn.execute(q_desp).fetchone()[0]
        folha = conn.execute(q_folha).fetchone()
    pro_labore = folha[0] if folha else 0
    inss = folha[1] if folha else 0
    liquido_folha = folha[2] if folha else 0
    conn.close()
    return jsonify({
        'faturamento_bruto': faturamento,
        'despesas_operacionais': despesas,
        'pro_labore_bruto': pro_labore,
        'inss': inss,
        'liquido_folha': liquido_folha,
        'resultado': faturamento - despesas - pro_labore
    })

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path and os.path.exists(os.path.join('public', path)):
        return send_from_directory('public', path)
    return send_from_directory('public', 'index.html')

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
