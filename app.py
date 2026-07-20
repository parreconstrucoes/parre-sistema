from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3, hashlib, jwt, os, datetime, json

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app, resources={r'/api/*': {'origins': '*'}}, supports_credentials=True)
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
        data_inicio TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    # Adicionar colunas se nao existirem (migration)
    try:
        c.execute("ALTER TABLE obras ADD COLUMN data_inicio TEXT")
    except:
        pass

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
    cur = conn.execute("""INSERT INTO obras (nome,condominio,rua,quadra,lote,cno,budget,valor_terreno,valor_venda,com_corretor,valor_corretor,imposto_venda,status,data_inicio)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d['nome'],d.get('condominio',''),d.get('rua',''),d.get('quadra',''),d.get('lote',''),
         d.get('cno',''),d.get('budget',0),d.get('valor_terreno',0),d.get('valor_venda',0),
         d.get('com_corretor',0),d.get('valor_corretor',0),d.get('imposto_venda',0),'Em andamento',
         d.get('data_inicio','')))
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
        valor_terreno=?,valor_venda=?,com_corretor=?,valor_corretor=?,imposto_venda=?,status=?,data_inicio=? WHERE id=?""",
        (d['nome'],d.get('condominio',''),d.get('rua',''),d.get('quadra',''),d.get('lote',''),
         d.get('cno',''),d.get('budget',0),d.get('valor_terreno',0),d.get('valor_venda',0),
         d.get('com_corretor',0),d.get('valor_corretor',0),d.get('imposto_venda',0),d.get('status','Em andamento'),
         d.get('data_inicio',''),id))
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


# ============ GERAÇÃO DE ORÇAMENTO PDF ============
@app.route('/api/gerar-orcamento', methods=['POST'])
@token_required
def gerar_orcamento_pdf():
    import tempfile, os
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    from flask import send_file

    d = request.json
    PRETO = colors.HexColor("#1A1A1A")
    CINZA_TXT = colors.HexColor("#7A7A7A")
    CINZA_BOX = colors.HexColor("#F4F4F4")
    CINZA_BORDA = colors.HexColor("#D9D9D9")
    styles = getSampleStyleSheet()

    def sty(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    style_empresa = sty("Empresa", fontSize=13, leading=15, textColor=PRETO, fontName="Helvetica-Bold")
    style_empresa_info = sty("EmpresaInfo", fontSize=8, leading=11, textColor=CINZA_TXT)
    style_numero = sty("Numero", fontSize=9, leading=11, textColor=CINZA_TXT, alignment=TA_RIGHT)
    style_titulo = sty("Titulo", fontSize=22, leading=26, textColor=PRETO, fontName="Helvetica-Bold", alignment=TA_CENTER)
    style_subtitulo = sty("Subtitulo", fontSize=10, leading=13, textColor=CINZA_TXT, alignment=TA_CENTER)
    style_secao = sty("Secao", fontSize=9.5, leading=12, textColor=PRETO, fontName="Helvetica-Bold")
    style_label = sty("Label", fontSize=7.5, leading=10, textColor=CINZA_TXT)
    style_valor = sty("Valor", fontSize=9.5, leading=12, textColor=PRETO, fontName="Helvetica-Bold")
    style_th = sty("TH", fontSize=9, leading=11, textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_CENTER)
    style_th_left = sty("THLeft", fontSize=9, leading=11, textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_LEFT)
    style_td = sty("TD", fontSize=9.5, leading=12, textColor=PRETO, alignment=TA_CENTER)
    style_td_left = sty("TDLeft", fontSize=9.5, leading=12, textColor=PRETO, fontName="Helvetica-Bold", alignment=TA_LEFT)
    style_total_label = sty("TotalLabel", fontSize=10.5, leading=13, textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_LEFT)
    style_total_valor = sty("TotalValor", fontSize=10.5, leading=13, textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_CENTER)
    style_rodape = sty("Rodape", fontSize=9, leading=12, textColor=PRETO)
    style_rodape_right = sty("RodapeRight", fontSize=9, leading=12, textColor=PRETO, alignment=TA_RIGHT)
    style_rodape_right_bold = sty("RodapeRightBold", fontSize=9, leading=12, textColor=PRETO, alignment=TA_RIGHT, fontName="Helvetica-Bold")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf', dir='/tmp')
    tmp.close()

    doc = SimpleDocTemplate(tmp.name, pagesize=A4, topMargin=16*mm, bottomMargin=16*mm, leftMargin=18*mm, rightMargin=18*mm)
    el = []

    # Logo como texto (P dourado em caixa preta) ou imagem se existir
    logo_path = os.path.join(os.path.dirname(__file__), 'public', 'logo.png')
    if os.path.exists(logo_path):
        from reportlab.platypus import Image
        logo_img = Image(logo_path, width=16*mm, height=16*mm)
    else:
        logo_img = Paragraph("<b>P</b>", sty("Logo", fontSize=14, textColor=colors.white, fontName="Helvetica-Bold", alignment=TA_CENTER))

    numero = d.get('numero', '000')
    titulo_servico = d.get('titulo_servico', '')
    cliente_razao_social = d.get('cliente_razao_social', '')
    cliente_cnpj = d.get('cliente_cnpj', '')
    cliente_endereco = d.get('cliente_endereco', '')
    tipo_servico = d.get('tipo_servico', '')
    material = d.get('material', 'Fornecido pelo contratante')
    valor_diaria_raw = d.get('valor_diaria', '')
    def _pv(v):
        v = str(v).strip().replace('R$','').replace('RS','').replace(' ','')
        v = v.replace('.','').replace(',','.') if (',' in v and '.' in v) else v.replace(',','.')
        try: return float(v)
        except: return 0.0
    _vd = _pv(valor_diaria_raw)
    _lbl = d.get('label_valor','')
    _sfx = ' / mes' if 'mensal' in _lbl.lower() or 'mes' in _lbl.lower() else ' / dia'
    valor_diaria = ('R$ {:,.2f}'.format(_vd).replace(',','X').replace('.',',').replace('X','.') + _sfx) if _vd > 0 else valor_diaria_raw
    label_valor = d.get('label_valor', 'Valor da Diária')
    itens = d.get('itens', [])
    total_geral_raw = d.get('total_geral', 'R$ 0,00')
    # Recalcular total no backend para garantir
    total_calc = 0.0
    for item in d.get('itens', []):
        _vv2 = str(item.get('valor','0')).strip().replace('R$','').replace('RS','').replace(' ','')
        _vv2 = _vv2.replace('.','').replace(',','.') if (',' in _vv2 and '.' in _vv2) else _vv2.replace(',','.')
        try: _vn2 = float(_vv2)
        except: _vn2 = 0.0
        total_calc += _vn2 * float(item.get('qtd', 1) or 1)
    total_geral = 'R$ {:,.2f}'.format(total_calc).replace(',','X').replace('.',',').replace('X','.')
    data_local = d.get('data_local', 'Sorocaba')
    validade = d.get('validade', '15 dias')
    observacoes = d.get('observacoes', None)

    info_empresa = Table(
        [[Paragraph("PARRE CONSTRUÇÕES LTDA", style_empresa)],
         [Paragraph("CNPJ: 65.793.940/0001-20", style_empresa_info)],
         [Paragraph("R. Alice Manrique Gabriel, 79 – Horto Florestal – Sorocaba/SP – CEP 18.074-752", style_empresa_info)],
         [Paragraph("(15) 99186-2039 | parreconstrucoes@gmail.com", style_empresa_info)]],
        colWidths=[doc.width - 22*mm],
    )
    info_empresa.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),1)]))

    cab = Table([[logo_img, info_empresa, Paragraph(f"Nº {numero}", style_numero)]],
        colWidths=[18*mm, doc.width - 18*mm - 22*mm, 22*mm])
    cab.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0)]))
    el.append(cab)
    el.append(Spacer(1, 8))

    def linha_sep():
        t = Table([[""]], colWidths=[doc.width], rowHeights=[1])
        t.setStyle(TableStyle([("LINEBELOW",(0,0),(-1,-1),0.75,CINZA_BORDA)]))
        return t

    el.append(linha_sep())
    el.append(Spacer(1, 14))
    el.append(Paragraph("PROPOSTA COMERCIAL", style_titulo))
    el.append(Paragraph(titulo_servico, style_subtitulo))
    el.append(Spacer(1, 6))
    el.append(linha_sep())
    el.append(Spacer(1, 14))

    el.append(Paragraph("CONTRATANTE", style_secao))
    el.append(Spacer(1, 5))
    box1 = Table(
        [[Paragraph("Razão Social", style_label), Paragraph("CNPJ", style_label)],
         [Paragraph(cliente_razao_social, style_valor), Paragraph(cliente_cnpj, style_valor)]],
        colWidths=[doc.width*0.65, doc.width*0.35])
    box1.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),CINZA_BOX),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,0),6),("BOTTOMPADDING",(0,1),(-1,1),6),("LINEBELOW",(0,0),(-1,0),0.5,CINZA_BORDA)]))
    el.append(box1)
    el.append(Spacer(1, 1))
    box2 = Table([[Paragraph("Endereço", style_label)],[Paragraph(cliente_endereco, style_valor)]], colWidths=[doc.width])
    box2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),CINZA_BOX),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(0,0),6),("BOTTOMPADDING",(0,1),(0,1),6),("LINEBELOW",(0,0),(-1,0),0.5,CINZA_BORDA)]))
    el.append(box2)
    el.append(Spacer(1, 14))

    el.append(Paragraph("CONDIÇÕES DO SERVIÇO", style_secao))
    el.append(Spacer(1, 5))
    box3 = Table(
        [[Paragraph("Tipo de Serviço", style_label), Paragraph("Material", style_label), Paragraph(label_valor, style_label)],
         [Paragraph(tipo_servico, style_valor), Paragraph(material, style_valor), Paragraph(valor_diaria, style_valor)]],
        colWidths=[doc.width/3]*3)
    box3.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),CINZA_BOX),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,0),6),("BOTTOMPADDING",(0,1),(-1,1),6),("LINEBELOW",(0,0),(-1,0),0.5,CINZA_BORDA)]))
    el.append(box3)
    el.append(Spacer(1, 14))

    el.append(Paragraph("DETALHAMENTO DO SERVIÇO", style_secao))
    el.append(Spacer(1, 6))
    cab_tab = [Paragraph("Descrição do Serviço", style_th_left), Paragraph("Data", style_th), Paragraph("Qtd", style_th), Paragraph("Un", style_th), Paragraph("Valor (R$)", style_th)]
    linhas_tab = [cab_tab]
    for item in itens:
        # Calcular valor formatado
        _vv = str(item.get('valor','0')).strip().replace('R$','').replace('RS','').replace(' ','')
        _vv = _vv.replace('.','').replace(',','.') if (',' in _vv and '.' in _vv) else _vv.replace(',','.')
        try: v_num = float(_vv)
        except: v_num = 0.0
        qtd_num = float(item.get('qtd', 1) or 1)
        v_total_item = v_num * qtd_num
        v_fmt = 'R$ {:,.2f}'.format(v_total_item).replace(',','X').replace('.',',').replace('X','.')
        linhas_tab.append([Paragraph(item.get('descricao',''), style_td_left), Paragraph(item.get('data',''), style_td), Paragraph(str(item.get('qtd',1)), style_td), Paragraph(item.get('unidade','Diária'), style_td), Paragraph(v_fmt, style_td)])
    n_itens = len(itens)
    linhas_tab.append([Paragraph("TOTAL GERAL", style_total_label), "", "", "", Paragraph(total_geral, style_total_valor)])
    tabela = Table(linhas_tab, colWidths=[doc.width*0.38, doc.width*0.27, doc.width*0.10, doc.width*0.10, doc.width*0.15])
    est = [("BACKGROUND",(0,0),(-1,0),PRETO),("SPAN",(0,n_itens+1),(3,n_itens+1)),("BACKGROUND",(0,n_itens+1),(-1,n_itens+1),PRETO),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),("LINEBELOW",(0,0),(-1,n_itens),0.5,CINZA_BORDA)]
    for i in range(1, n_itens+1):
        if i % 2 == 0:
            est.append(("BACKGROUND",(0,i),(-1,i),CINZA_BOX))
    tabela.setStyle(TableStyle(est))
    el.append(tabela)
    el.append(Spacer(1, 14))

    if observacoes:
        el.append(Paragraph("OBSERVAÇÕES", style_secao))
        el.append(Spacer(1, 5))
        box_obs = Table([[Paragraph(observacoes, style_valor)]], colWidths=[doc.width])
        box_obs.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),CINZA_BOX),("LEFTPADDING",(0,0),(-1,-1),8),("RIGHTPADDING",(0,0),(-1,-1),8),("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7)]))
        el.append(box_obs)
        el.append(Spacer(1, 14))
    else:
        el.append(Spacer(1, 12))

    rodape = Table(
        [[Paragraph(data_local, style_rodape), Paragraph("Parre Construções Ltda.", style_rodape_right_bold)],
         [Paragraph(f"Validade desta proposta: {validade}", style_valor), Paragraph("CNPJ: 65.793.940/0001-20", style_rodape_right)]],
        colWidths=[doc.width/2, doc.width/2])
    rodape.setStyle(TableStyle([("LEFTPADDING",(0,0),(-1,-1),0),("RIGHTPADDING",(0,0),(-1,-1),0),("TOPPADDING",(0,0),(-1,-1),2),("LINEABOVE",(0,0),(-1,0),0.5,CINZA_BORDA)]))
    el.append(rodape)
    doc.build(el)

    return send_file(tmp.name, as_attachment=True, download_name=f"Proposta_{numero}.pdf", mimetype='application/pdf')


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
