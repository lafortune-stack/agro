from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Text, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel
import datetime
import random
from typing import Optional

# --- 1. CONFIGURATION DB ---
DB_USER = "lucress"
DB_PASS = "ton_mot_de_passe" # <--- METS TON VRAI MOT DE PASSE POSTGRES ICI
DB_NAME = "agro_db"
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@localhost/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="AgroStat Pro")

# --- 2. MODÈLE DB ---
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

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# Initialisation de la base
@app.on_event("startup")
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if db.query(DonneeAgricole).count() == 0:
        for i in range(10):
            db.add(DonneeAgricole(
                producteur=random.choice(["Moussa", "Sita", "Lucress", "Jean"]),
                culture=random.choice(["Cacao", "Café", "Maïs"]),
                quantite=round(random.uniform(100, 500), 2),
                localisation="Zone Centrale"
            ))
        db.commit()
    db.close()

# --- 3. API (CORRIGÉE : SANS CLÉ API) ---

@app.get("/api/collecte")
def lister(search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(DonneeAgricole)
    if search:
        query = query.filter(DonneeAgricole.producteur.ilike(f"%{search}%"))
    return query.order_by(DonneeAgricole.id.desc()).all()

@app.post("/api/collecte")
def creer(data: CollecteCreate, db: Session = Depends(get_db)):
    # Suppression de la vérification de la clé secrète ici
    n = DonneeAgricole(**data.dict())
    db.add(n)
    db.commit()
    return {"status": "success"}

@app.delete("/api/collecte/{id}")
def supprimer(id: int, db: Session = Depends(get_db)):
    # Suppression de la vérification de la clé secrète ici
    item = db.query(DonneeAgricole).filter(DonneeAgricole.id == id).first()
    if item:
        db.delete(item)
        db.commit()
    return {"status": "deleted"}

@app.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    res = db.query(DonneeAgricole.culture, func.sum(DonneeAgricole.quantite)).group_by(DonneeAgricole.culture).all()
    return {"labels": [r[0] for r in res], "values": [r[1] for r in res]}

# --- 4. FRONTEND (SPA) ---
@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <title>AgroStat Dashboard</title>
        <style>
            .active-link { background-color: #16a34a; color: white; }
        </style>
    </head>
    <body class="bg-gray-50 flex h-screen overflow-hidden text-slate-800">

        <div class="w-64 bg-slate-900 text-white flex flex-col shadow-xl">
            <div class="p-6 text-2xl font-bold border-b border-slate-700 text-green-400">🌾 AgroStat</div>
            <nav class="flex-1 p-4 space-y-2 mt-4">
                <button onclick="showPage('stats')" id="btn-stats" class="w-full text-left p-3 rounded transition hover:bg-slate-800">📊 Dashboard</button>
                <button onclick="showPage('list')" id="btn-list" class="w-full text-left p-3 rounded transition hover:bg-slate-800">📋 Membres</button>
                <button onclick="showPage('add')" id="btn-add" class="w-full text-left p-3 rounded transition hover:bg-slate-800">➕ Nouvelle Saisie</button>
                <button onclick="showPage('search')" id="btn-search" class="w-full text-left p-3 rounded transition hover:bg-slate-800">🔍 Recherche</button>
            </nav>
            <div class="p-4 text-xs text-slate-500 border-t border-slate-700 text-center">© 2026 Dashboard Agricole</div>
        </div>

        <div class="flex-1 flex flex-col overflow-y-auto">
            <header class="bg-white shadow-sm p-6 flex justify-between items-center sticky top-0 z-20">
                <h2 id="page-title" class="text-xl font-semibold">Dashboard</h2>
                <div class="flex items-center gap-2"><span class="w-3 h-3 bg-green-500 rounded-full animate-pulse"></span> Serveur en ligne</div>
            </header>

            <main class="p-8">
                <div id="page-stats" class="page-content hidden grid grid-cols-1 md:grid-cols-2 gap-8">
                    <div class="bg-white p-6 rounded-2xl shadow-sm border"><h3 class="font-bold mb-4">Production par Culture (kg)</h3><canvas id="chartPie"></canvas></div>
                    <div class="bg-white p-6 rounded-2xl shadow-sm border"><h3 class="font-bold mb-4">Volume total collecté</h3><canvas id="chartBar"></canvas></div>
                </div>

                <div id="page-list" class="page-content hidden bg-white rounded-2xl shadow-sm border overflow-hidden">
                    <table class="w-full text-left">
                        <thead class="bg-slate-50 border-b font-bold text-slate-500 uppercase text-xs">
                            <tr><th class="p-4">Producteur</th><th class="p-4">Culture</th><th class="p-4">Poids (kg)</th><th class="p-4">Action</th></tr>
                        </thead>
                        <tbody id="table-body" class="divide-y"></tbody>
                    </table>
                </div>

                <div id="page-add" class="page-content hidden max-w-lg mx-auto bg-white p-8 rounded-2xl shadow-md border">
                    <h3 class="text-xl font-bold mb-6 text-green-700">Enregistrer une récolte</h3>
                    <div class="space-y-4">
                        <input id="inp-p" placeholder="Nom du Producteur" class="w-full p-3 border rounded-xl outline-none focus:ring-2 focus:ring-green-400">
                        <select id="inp-c" class="w-full p-3 border rounded-xl outline-none"><option>Cacao</option><option>Café</option><option>Maïs</option></select>
                        <input id="inp-q" type="number" placeholder="Poids en Kg" class="w-full p-3 border rounded-xl outline-none">
                        <input id="inp-l" placeholder="Lieu de récolte" class="w-full p-3 border rounded-xl outline-none">
                        <button onclick="submitForm()" class="w-full bg-green-600 text-white py-3 rounded-xl font-bold hover:bg-green-700 shadow-lg">Valider</button>
                    </div>
                </div>

                <div id="page-search" class="page-content hidden space-y-6">
                    <input id="search-input" oninput="doSearch()" placeholder="Rechercher un producteur..." class="w-full p-4 border rounded-2xl shadow-sm outline-none focus:ring-2 focus:ring-green-500">
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
                const titles = {stats:'Tableau de Bord', list:'Registre des Membres', add:'Nouvelle Saisie', search:'Recherche Avancée'};
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
                charts.pie = new Chart(ctxPie, { type:'doughnut', data:{ labels:res.labels, datasets:[{data:res.values, backgroundColor:['#10b981','#3b82f6','#f59e0b']}] } });
                charts.bar = new Chart(ctxBar, { type:'bar', data:{ labels:res.labels, datasets:[{label:'Poids (kg)', data:res.values, backgroundColor:'#16a34a'}] } });
            }

            async function loadList() {
                const data = await fetch('/api/collecte').then(r => r.json());
                document.getElementById('table-body').innerHTML = data.map(i => `
                    <tr class="hover:bg-slate-50 transition">
                        <td class="p-4 font-bold text-slate-700">${i.producteur}</td>
                        <td class="p-4"><span class="bg-green-100 text-green-700 px-2 py-1 rounded text-xs font-bold">${i.culture}</span></td>
                        <td class="p-4 font-mono font-bold">${i.quantite} kg</td>
                        <td class="p-4"><button onclick="deleteItem(${i.id})" class="bg-red-50 text-red-500 p-2 rounded-lg hover:bg-red-100 transition">🗑️</button></td>
                    </tr>
                `).join('');
            }

            async function doSearch() {
                const val = document.getElementById('search-input').value;
                const data = await fetch('/api/collecte?search=' + val).then(r => r.json());
                document.getElementById('search-results').innerHTML = data.map(i => `
                    <div class="bg-white p-6 rounded-2xl shadow-sm border-t-4 border-green-500">
                        <p class="font-bold text-xl">${i.producteur}</p>
                        <p class="text-sm text-slate-500 mb-4">${i.culture} • ${i.localisation}</p>
                        <div class="text-green-600 font-bold text-lg">${i.quantite} kg</div>
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
                if(!body.producteur || isNaN(body.quantite)) return alert("Remplissez tous les champs !");
                const res = await fetch('/api/collecte', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
                if(res.ok) { alert("Enregistré avec succès !"); showPage('list'); }
            }

            async function deleteItem(id) {
                if(confirm("Supprimer ce membre ?")) {
                    await fetch('/api/collecte/' + id, { method:'DELETE' });
                    loadList();
                }
            }

            showPage('stats');
        </script>
    </body>
    </html>
    """