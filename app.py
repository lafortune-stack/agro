import os
import datetime
import random
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel

# --- 1. CONFIGURATION DE LA BASE DE DONNÉES ---

# Render fournit la variable DATABASE_URL automatiquement si tu l'as ajoutée
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Correctif indispensable pour SQLAlchemy sur Render
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    # CONFIGURATION LOCALE (Ton PC)
    DB_USER = "lucress"
    DB_PASS = "ton_mot_de_passe" # Remplace par ton mot de passe local
    DB_NAME = "agro_db"
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@localhost/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="AgroStat Pro")

# --- 2. MODÈLE DE DONNÉES ---

class DonneeAgricole(Base):
    __tablename__ = "collecte_agricole"
    id = Column(Integer, primary_key=True, index=True)
    producteur = Column(String(100))
    culture = Column(String(100))
    quantite = Column(Float)
    localisation = Column(String(200))
    date_collecte = Column(DateTime, default=datetime.datetime.utcnow)

class CollecteCreate(BaseModel):
    producteur: str
    culture: str
    quantite: float
    localisation: str

# Dépendance pour la session DB
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Création des tables et injection de données de test au démarrage
@app.on_event("startup")
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if db.query(DonneeAgricole).count() == 0:
        noms = ["Moussa", "Sita", "Lucress", "Jean", "Awa"]
        cultures = ["Cacao", "Café", "Maïs", "Ananas"]
        for i in range(10):
            db.add(DonneeAgricole(
                producteur=random.choice(noms),
                culture=random.choice(cultures),
                quantite=round(random.uniform(100, 600), 2),
                localisation="Zone Agricole " + str(random.randint(1, 5))
            ))
        db.commit()
    db.close()

# --- 3. POINTS D'ACCÈS API (BACKEND) ---

@app.get("/api/collecte")
def lister_et_rechercher(search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(DonneeAgricole)
    if search:
        query = query.filter(DonneeAgricole.producteur.ilike(f"%{search}%"))
    return query.order_by(DonneeAgricole.id.desc()).all()

@app.post("/api/collecte")
def creer_collecte(data: CollecteCreate, db: Session = Depends(get_db)):
    nouvelle_entree = DonneeAgricole(**data.dict())
    db.add(nouvelle_entree)
    db.commit()
    return {"status": "success"}

@app.delete("/api/collecte/{id}")
def supprimer_collecte(id: int, db: Session = Depends(get_db)):
    item = db.query(DonneeAgricole).filter(DonneeAgricole.id == id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Membre non trouvé")
    db.delete(item)
    db.commit()
    return {"status": "deleted"}

@app.get("/api/stats")
def obtenir_stats(db: Session = Depends(get_db)):
    res = db.query(DonneeAgricole.culture, func.sum(DonneeAgricole.quantite)).group_by(DonneeAgricole.culture).all()
    return {
        "labels": [r[0] for r in res],
        "values": [float(r[1]) for r in res]
    }

# --- 4. INTERFACE UTILISATEUR (FRONTEND SPA) ---

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <title>AgroStat Dashboard Pro</title>
        <style>
            .active-link { background-color: #16a34a; color: white; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); }
        </style>
    </head>
    <body class="bg-slate-50 flex h-screen overflow-hidden text-slate-800 font-sans">

        <div class="w-64 bg-slate-900 text-white flex flex-col shadow-2xl z-30">
            <div class="p-8 text-2xl font-black border-b border-slate-800 text-green-500 tracking-tighter italic">
                🌾 AgroStat
            </div>
            <nav class="flex-1 p-4 space-y-3 mt-6">
                <button onclick="showPage('stats')" id="btn-stats" class="w-full text-left p-4 rounded-xl transition-all duration-200 hover:bg-slate-800 flex items-center gap-3">📊 Tableau de Bord</button>
                <button onclick="showPage('list')" id="btn-list" class="w-full text-left p-4 rounded-xl transition-all duration-200 hover:bg-slate-800 flex items-center gap-3">📋 Liste des Membres</button>
                <button onclick="showPage('add')" id="btn-add" class="w-full text-left p-4 rounded-xl transition-all duration-200 hover:bg-slate-800 flex items-center gap-3">➕ Nouvelle Saisie</button>
                <button onclick="showPage('search')" id="btn-search" class="w-full text-left p-4 rounded-xl transition-all duration-200 hover:bg-slate-800 flex items-center gap-3">🔍 Rechercher</button>
            </nav>
            <div class="p-6 text-xs text-slate-500 border-t border-slate-800 text-center font-medium uppercase tracking-widest">
                Lucress Agro • 2026
            </div>
        </div>

        <div class="flex-1 flex flex-col overflow-y-auto">
            <header class="bg-white/80 backdrop-blur-md shadow-sm p-6 flex justify-between items-center sticky top-0 z-20 border-b border-slate-100">
                <h2 id="page-title" class="text-2xl font-bold text-slate-800">Chargement...</h2>
                <div class="flex items-center gap-4">
                    <span class="px-3 py-1 bg-green-100 text-green-700 text-xs font-black rounded-full uppercase tracking-tighter">En ligne</span>
                </div>
            </header>

            <main class="p-8 lg:p-12">
                <div id="page-stats" class="page-content hidden grid grid-cols-1 md:grid-cols-2 gap-10">
                    <div class="bg-white p-8 rounded-3xl shadow-sm border border-slate-100 transition-transform hover:scale-[1.01]">
                        <h3 class="font-bold mb-6 text-slate-500 uppercase text-xs tracking-widest">Répartition par Culture</h3>
                        <canvas id="chartPie"></canvas>
                    </div>
                    <div class="bg-white p-8 rounded-3xl shadow-sm border border-slate-100 transition-transform hover:scale-[1.01]">
                        <h3 class="font-bold mb-6 text-slate-500 uppercase text-xs tracking-widest">Volume total (kg)</h3>
                        <canvas id="chartBar"></canvas>
                    </div>
                </div>

                <div id="page-list" class="page-content hidden bg-white rounded-3xl shadow-sm border border-slate-100 overflow-hidden">
                    <table class="w-full text-left border-collapse">
                        <thead class="bg-slate-50/50 border-b border-slate-100 font-bold text-slate-400 uppercase text-[10px] tracking-widest">
                            <tr>
                                <th class="p-6">Producteur</th>
                                <th class="p-6">Culture</th>
                                <th class="p-6">Quantité</th>
                                <th class="p-6 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody id="table-body" class="divide-y divide-slate-50"></tbody>
                    </table>
                </div>

                <div id="page-add" class="page-content hidden max-w-xl mx-auto bg-white p-10 rounded-3xl shadow-xl border border-slate-100">
                    <h3 class="text-2xl font-black mb-8 text-slate-800">Enregistrer une collecte</h3>
                    <div class="space-y-5">
                        <div>
                            <label class="text-xs font-bold text-slate-400 uppercase mb-2 block">Producteur</label>
                            <input id="inp-p" placeholder="Ex: Moussa Traoré" class="w-full p-4 bg-slate-50 border-none rounded-2xl outline-none focus:ring-2 focus:ring-green-500 transition-all">
                        </div>
                        <div class="grid grid-cols-2 gap-4">
                            <div>
                                <label class="text-xs font-bold text-slate-400 uppercase mb-2 block">Culture</label>
                                <select id="inp-c" class="w-full p-4 bg-slate-50 border-none rounded-2xl outline-none focus:ring-2 focus:ring-green-500 transition-all">
                                    <option>Cacao</option><option>Café</option><option>Maïs</option><option>Ananas</option>
                                </select>
                            </div>
                            <div>
                                <label class="text-xs font-bold text-slate-400 uppercase mb-2 block">Poids (Kg)</label>
                                <input id="inp-q" type="number" placeholder="0.00" class="w-full p-4 bg-slate-50 border-none rounded-2xl outline-none focus:ring-2 focus:ring-green-500 transition-all">
                            </div>
                        </div>
                        <div>
                            <label class="text-xs font-bold text-slate-400 uppercase mb-2 block">Localisation</label>
                            <input id="inp-l" placeholder="Ex: Région de l'Est" class="w-full p-4 bg-slate-50 border-none rounded-2xl outline-none focus:ring-2 focus:ring-green-500 transition-all">
                        </div>
                        <button onclick="submitForm()" class="w-full bg-green-600 text-white py-5 rounded-2xl font-black text-lg hover:bg-green-700 shadow-lg shadow-green-200 transition-all active:scale-95 mt-4">Confirmer l'ajout</button>
                    </div>
                </div>

                <div id="page-search" class="page-content hidden space-y-8">
                    <div class="relative group">
                        <span class="absolute left-6 top-1/2 -translate-y-1/2 text-xl">🔍</span>
                        <input id="search-input" oninput="doSearch()" placeholder="Commencez à taper le nom d'un producteur..." class="w-full p-6 pl-16 bg-white border border-slate-100 rounded-3xl shadow-sm outline-none focus:ring-2 focus:ring-green-500 transition-all text-lg font-medium">
                    </div>
                    <div id="search-results" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"></div>
                </div>
            </main>
        </div>

        <script>
            let charts = {};

            function showPage(pageId) {
                document.querySelectorAll('.page-content').forEach(p => p.classList.add('hidden'));
                document.querySelectorAll('nav button').forEach(b => b.classList.remove('active-link'));
                document.getElementById('page-' + pageId).classList.remove('hidden');
                document.getElementById('btn-' + pageId).classList.add('active-link');
                
                const titles = {stats:'Analyses Graphiques', list:'Registre des Membres', add:'Nouvelle Saisie', search:'Moteur de Recherche'};
                document.getElementById('page-title').innerText = titles[pageId];
                
                if(pageId === 'stats') loadStats();
                if(pageId === 'list') loadList();
            }

            async function loadStats() {
                const res = await fetch('/api/stats').then(r => r.json());
                const ctxPie = document.getElementById('chartPie').getContext('2d');
                const ctxBar = document.getElementById('chartBar').getContext('2d');
                
                if(charts.pie) charts.pie.destroy();
                if(charts.bar) charts.bar.destroy();
                
                const colors = ['#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6'];
                
                charts.pie = new Chart(ctxPie, { 
                    type:'doughnut', 
                    data:{ labels:res.labels, datasets:[{data:res.values, backgroundColor:colors, borderWidth:0}] },
                    options: { cutout: '70%', plugins: { legend: { position: 'bottom' } } }
                });
                
                charts.bar = new Chart(ctxBar, { 
                    type:'bar', 
                    data:{ labels:res.labels, datasets:[{label:'Stock (Kg)', data:res.values, backgroundColor:'#16a34a', borderRadius: 8}] },
                    options: { scales: { y: { beginAtZero: true } } }
                });
            }

            async function loadList() {
                const data = await fetch('/api/collecte').then(r => r.json());
                document.getElementById('table-body').innerHTML = data.map(i => `
                    <tr class="hover:bg-slate-50/50 transition-colors">
                        <td class="p-6 font-extrabold text-slate-700">${i.producteur}</td>
                        <td class="p-6"><span class="bg-green-100 text-green-700 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-tighter">${i.culture}</span></td>
                        <td class="p-6 font-mono font-bold text-slate-600">${i.quantite} kg</td>
                        <td class="p-6 text-right">
                            <button onclick="deleteItem(${i.id})" class="text-slate-300 hover:text-red-500 transition-colors text-xl">🗑️</button>
                        </td>
                    </tr>
                `).join('');
            }

            async function doSearch() {
                const val = document.getElementById('search-input').value;
                if(val.length < 1) { document.getElementById('search-results').innerHTML = ''; return; }
                const data = await fetch('/api/collecte?search=' + val).then(r => r.json());
                document.getElementById('search-results').innerHTML = data.map(i => `
                    <div class="bg-white p-6 rounded-3xl shadow-sm border border-slate-100 border-l-8 border-l-green-500 animate-in fade-in zoom-in duration-300">
                        <p class="font-black text-xl text-slate-800">${i.producteur}</p>
                        <p class="text-xs font-bold text-slate-400 uppercase mt-1 mb-4">${i.culture} • ${i.localisation}</p>
                        <div class="flex justify-between items-center">
                            <span class="text-green-600 font-black text-2xl">${i.quantite} <small class="text-xs">kg</small></span>
                        </div>
                    </div>
                `).join('');
            }

            async function submitForm() {
                const body = {
                    producteur: document.getElementById('inp-p').value,
                    culture: document.getElementById('inp-c').value,
                    quantite: parseFloat(document.getElementById('inp-q').value),
                    localisation: document.getElementById('inp-l').value
                };
                if(!body.producteur || isNaN(body.quantite)) return alert("Veuillez remplir correctement tous les champs.");
                
                const res = await fetch('/api/collecte', { 
                    method:'POST', 
                    headers:{'Content-Type':'application/json'}, 
                    body:JSON.stringify(body) 
                });
                
                if(res.ok) { 
                    alert("Collecte enregistrée !"); 
                    showPage('list');
                    // Reset fields
                    document.getElementById('inp-p').value = '';
                    document.getElementById('inp-q').value = '';
                    document.getElementById('inp-l').value = '';
                }
            }

            async function deleteItem(id) {
                if(confirm("Confirmer la suppression de cet enregistrement ?")) {
                    await fetch('/api/collecte/' + id, { method:'DELETE' });
                    loadList();
                }
            }

            // Initialisation au démarrage
            showPage('stats');
        </script>
    </body>
    </html>
    """