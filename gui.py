#!/usr/bin/env python3
"""Transport Document Processor — Professional GUI (v3.0)"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading, os, sys, json, csv, tempfile, webbrowser
from pathlib import Path
from extractors.pdf_reader import PDFReader
from extractors.regex_extractor import RegexExtractor
from extractors.data_processor import DataProcessor
from extractors.city_extractor import CityExtractor
from extractors.google_sheets_exporter import GoogleSheetsExporter
from database.db_manager import DatabaseManager
from config import (GOOGLE_SHEET_ID, CREDENTIALS_FILE, ENABLE_SHEETS_EXPORT,
                    DB_PATH, DEFAULT_EUR_PLN_RATE)
try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# ── Design System ──
if sys.platform == 'darwin':
    FF, FM = 'SF Pro Display', 'SF Mono'
elif sys.platform == 'win32':
    FF, FM = 'Segoe UI', 'Consolas'
else:
    FF, FM = 'Helvetica', 'Courier'
F = {
    'h1': (FF,18,'bold'), 'h2': (FF,14,'bold'), 'h3': (FF,12,'bold'),
    'body': (FF,12), 'sm': (FF,11), 'cap': (FF,10),
    'metric': (FF,20,'bold'), 'mlbl': (FF,10),
    'btn': (FF,12,'bold'), 'mono': (FM,11),
    'th': (FF,11,'bold'), 'td': (FF,11),
}
C = {
    'bg': '#FFFFFF', 'bg2': '#F8F9FA', 'bg3': '#F1F3F5',
    'tx': '#212529', 'tx2': '#6C757D', 'tx3': '#ADB5BD', 'txw': '#FFFFFF',
    'brd': '#E9ECEF', 'brd2': '#DEE2E6', 'focus': '#4C9AFF',
    'acc': '#4C9AFF', 'ach': '#3D8BF2', 'abg': '#EBF3FF',
    'ok': '#40C057', 'okb': '#EBFBEE', 'okt': '#2B8A3E',
    'warn': '#FD7E14', 'wrnb': '#FFF4E6', 'wrnt': '#D9480F',
    'err': '#FA5252', 'errb': '#FFF5F5', 'errt': '#C92A2A',
    'inf': '#339AF0', 'infb': '#E7F5FF', 'inft': '#1864AB',
    'sel': '#DBEAFE', 'self': '#1E3A5F',
}

def _pbtn(**kw):
    d = dict(font=F['btn'],bg=C['acc'],fg=C['txw'],relief=tk.FLAT,bd=0,padx=20,pady=10,
             cursor='hand2',activebackground=C['ach'],activeforeground=C['txw'],highlightthickness=0)
    d.update(kw); return d
def _sbtn(**kw):
    d = dict(font=F['body'],bg=C['bg'],fg=C['tx'],relief=tk.SOLID,bd=1,padx=16,pady=8,
             cursor='hand2',activebackground=C['bg2'],highlightthickness=0)
    d.update(kw); return d
def _dbtn(**kw):
    d = dict(font=F['body'],bg=C['bg'],fg=C['err'],relief=tk.SOLID,bd=1,padx=16,pady=8,
             cursor='hand2',activebackground=C['errb'],highlightthickness=0)
    d.update(kw); return d
def _gbtn(**kw):
    d = dict(font=F['body'],bg=C['bg3'],fg=C['tx2'],relief=tk.FLAT,bd=0,padx=12,pady=8,
             cursor='hand2',activebackground=C['brd'],highlightthickness=0)
    d.update(kw); return d

def _focus(e): e.widget.focus_set()
def _dlg_setup(dlg):
    dlg.focus_force(); dlg.lift()
    dlg.attributes('-topmost', True)
    dlg.after(100, lambda: dlg.attributes('-topmost', False))


class TransportGUI:
    def __init__(self):
        self.window = tk.Tk()
        self.window.title("Transport Extractor")
        self.window.geometry("1200x820")
        self.window.minsize(1100, 750)
        self.window.configure(bg=C['bg3'])
        self.processing = False; self.stop_requested = False
        self.current_folder = self._load_folder()
        self.regex_extractor = RegexExtractor()
        self.data_processor = DataProcessor()
        self.city_extractor = CityExtractor(use_spacy=True)
        self.sheets_exporter = None
        self.db = DatabaseManager(DB_PATH)
        self._week_data = {}; self._current_wt_id = None
        self._style(); self._ui()
        self._check_creds()

    def _style(self):
        s = ttk.Style(); s.theme_use('default')
        s.configure('TNotebook', background=C['bg3'], borderwidth=0)
        s.configure('TNotebook.Tab', font=F['body'], padding=[16,8],
                    background=C['bg3'], foreground=C['tx2'], borderwidth=0)
        s.map('TNotebook.Tab',
              background=[('selected',C['bg'])], foreground=[('selected',C['acc'])],
              font=[('selected',F['h3'])])
        s.configure('Treeview', font=F['td'], rowheight=34, background=C['bg'],
                    foreground=C['tx'], fieldbackground=C['bg'], borderwidth=0, relief=tk.FLAT)
        s.configure('Treeview.Heading', font=F['th'], background=C['bg2'],
                    foreground=C['tx2'], borderwidth=0, relief=tk.FLAT, padding=[8,6])
        s.map('Treeview', background=[('selected',C['sel'])], foreground=[('selected',C['self'])])
        s.configure('TProgressbar', troughcolor=C['brd'], background=C['acc'], thickness=6)

    def _ui(self):
        # Header
        hdr = tk.Frame(self.window, bg=C['bg'], height=48)
        hdr.pack(fill=tk.X); hdr.pack_propagate(False)
        tk.Label(hdr, text="Transport Extractor", font=F['h1'],
                 bg=C['bg'], fg=C['tx']).pack(side=tk.LEFT, padx=20, pady=10)
        tk.Label(hdr, text="agdar.it", font=F['cap'],
                 bg=C['bg'], fg=C['tx3']).pack(side=tk.RIGHT, padx=20)
        tk.Frame(self.window, bg=C['brd'], height=1).pack(fill=tk.X)
        # Tabs
        self.nb = ttk.Notebook(self.window)
        self.nb.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self.t1 = tk.Frame(self.nb, bg=C['bg3'])
        self.t2 = tk.Frame(self.nb, bg=C['bg'])
        self.t3 = tk.Frame(self.nb, bg=C['bg'])
        self.nb.add(self.t1, text="  Processing  ")
        self.nb.add(self.t2, text="  Database  ")
        self.nb.add(self.t3, text="  Statistics  ")
        self._t1(); self._t2(); self._t3()
        self.nb.bind("<<NotebookTabChanged>>", self._tab)

    # ═══════ TAB 1: PROCESSING ═══════
    def _t1(self):
        t = self.t1; pad = dict(padx=20)
        # Section title
        tk.Label(t, text="PDF folder", font=F['h3'], bg=C['bg3'], fg=C['tx2']).pack(
            anchor=tk.W, **pad, pady=(16,4))
        # Path row
        pf = tk.Frame(t, bg=C['bg3']); pf.pack(fill=tk.X, **pad, pady=(0,12))
        self.folder_var = tk.StringVar(value=self.current_folder or "No folder selected")
        tk.Entry(pf, textvariable=self.folder_var, font=F['mono'], state="readonly",
                 bg=C['bg'], fg=C['tx'], relief=tk.FLAT, bd=0, readonlybackground=C['bg2'],
                 highlightthickness=1, highlightbackground=C['brd2'],
                 selectbackground=C['sel'], selectforeground=C['self']
                 ).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8)
        tk.Button(pf, text="Browse", command=self._browse, **_sbtn()).pack(side=tk.LEFT, padx=(8,0))
        self.pdf_lbl = tk.Label(t, text="", font=F['sm'], bg=C['bg3'], fg=C['tx2'])
        self.pdf_lbl.pack(anchor=tk.W, **pad)
        # Actions
        af = tk.Frame(t, bg=C['bg3']); af.pack(fill=tk.X, **pad, pady=(8,4))
        self.proc_btn = tk.Button(af, text="Process && save", command=self._on_proc, **_pbtn())
        self.proc_btn.pack(side=tk.LEFT, padx=(0,8))
        self.stop_btn = tk.Button(af, text="Stop", command=self._stop, state=tk.DISABLED, **_dbtn())
        self.stop_btn.pack(side=tk.LEFT, padx=(0,8))
        self.sh_var = tk.BooleanVar(value=ENABLE_SHEETS_EXPORT and Path(CREDENTIALS_FILE).exists())
        self.sh_cb = tk.Checkbutton(af, text="Also export to Google Sheets", variable=self.sh_var,
                                    font=F['sm'], bg=C['bg3'], fg=C['tx2'], selectcolor=C['bg'],
                                    activebackground=C['bg3'])
        self.sh_cb.pack(side=tk.LEFT, padx=12)
        tk.Button(af, text="Open Sheets", command=self._open_sheets, **_gbtn()).pack(side=tk.RIGHT)
        # Progress
        tk.Label(t, text="Output", font=F['h3'], bg=C['bg3'], fg=C['tx2']).pack(
            anchor=tk.W, **pad, pady=(12,4))
        self.pbar = ttk.Progressbar(t, mode='indeterminate', length=700)
        self.pbar.pack(fill=tk.X, **pad, pady=(0,6))
        self.log_t = scrolledtext.ScrolledText(t, font=F['mono'], wrap=tk.WORD, height=14,
            bg=C['bg'], fg=C['tx'], relief=tk.FLAT, bd=0,
            highlightthickness=1, highlightbackground=C['brd2'], state=tk.DISABLED,
            selectbackground=C['sel'], selectforeground=C['self'])
        self.log_t.pack(fill=tk.BOTH, expand=True, **pad, pady=(0,8))
        self.log_t.tag_config("success", foreground=C['okt'])
        self.log_t.tag_config("error", foreground=C['errt'])
        self.log_t.tag_config("warning", foreground=C['wrnt'])
        self.log_t.tag_config("info", foreground=C['inft'])
        self.sum_lbl = tk.Label(t, text="Ready", font=F['body'], bg=C['bg3'], fg=C['tx2'])
        self.sum_lbl.pack(pady=(0,8))
        self._log("Select a folder with PDFs to begin.", "info")
        if self.current_folder: self._scan()

    # ═══════ TAB 2: DATABASE ═══════
    def _t2(self):
        t = self.t2
        # Controls
        ctrl = tk.Frame(t, bg=C['bg']); ctrl.pack(fill=tk.X, padx=16, pady=(12,8))
        tk.Label(ctrl, text="Truck", font=F['cap'], bg=C['bg'], fg=C['tx2']).pack(side=tk.LEFT, padx=(0,6))
        self.trk_var = tk.StringVar(value="Select truck...")
        self.trk_menu = tk.OptionMenu(ctrl, self.trk_var, "")
        self.trk_menu.config(font=F['body'], width=16, bg=C['bg'], fg=C['tx'], relief=tk.SOLID, bd=1,
                             activebackground=C['abg'], activeforeground=C['tx'], highlightthickness=0)
        self.trk_menu['menu'].config(font=F['body'], bg=C['bg'], fg=C['tx'],
                                      activebackground=C['acc'], activeforeground=C['txw'])
        self.trk_menu.pack(side=tk.LEFT, padx=(0,16))
        self.trk_var.trace_add('write', lambda *_: self._trk_sel(None))
        tk.Label(ctrl, text="Week", font=F['cap'], bg=C['bg'], fg=C['tx2']).pack(side=tk.LEFT, padx=(0,6))
        self.wk_var = tk.StringVar(value="Select week...")
        self.wk_menu = tk.OptionMenu(ctrl, self.wk_var, "")
        self.wk_menu.config(font=F['body'], width=12, bg=C['bg'], fg=C['tx'], relief=tk.SOLID, bd=1,
                            activebackground=C['abg'], activeforeground=C['tx'], highlightthickness=0)
        self.wk_menu['menu'].config(font=F['body'], bg=C['bg'], fg=C['tx'],
                                     activebackground=C['acc'], activeforeground=C['txw'])
        self.wk_menu.pack(side=tk.LEFT, padx=(0,16))
        self.wk_var.trace_add('write', lambda *_: self._wk_sel(None))
        tk.Button(ctrl, text="Add week", command=self._add_wk, **_sbtn()).pack(side=tk.LEFT, padx=4)
        tk.Button(ctrl, text="Delete week", command=self._del_wk, **_dbtn()).pack(side=tk.LEFT, padx=4)
        tk.Button(ctrl, text="Refresh", command=self._ref_db, **_gbtn()).pack(side=tk.RIGHT)
        tk.Frame(t, bg=C['brd'], height=1).pack(fill=tk.X, padx=16)
        # Week params as metric cards
        tk.Label(t, text="Week parameters", font=F['cap'], bg=C['bg'], fg=C['tx2']).pack(
            anchor=tk.W, padx=16, pady=(10,4))
        pf = tk.Frame(t, bg=C['bg']); pf.pack(fill=tk.X, padx=16, pady=(0,8))
        self.wv = {}
        params = [("KM total","km_total","km"),("Fuel refueled","fuel_refueled","L"),
                  ("KM in Germany","km_in_germany","km"),("EUR/PLN rate","eur_pln_rate",""),
                  ("Extra highway","extra_highway_charge_eur","EUR")]
        for i,(lbl,key,unit) in enumerate(params):
            card = tk.Frame(pf, bg=C['bg2'], padx=12, pady=8,
                           highlightthickness=1, highlightbackground=C['brd'])
            card.grid(row=0, column=i, padx=4, sticky=tk.NSEW)
            pf.columnconfigure(i, weight=1)
            tk.Label(card, text=lbl, font=F['mlbl'], bg=C['bg2'], fg=C['tx2']).pack(anchor=tk.W)
            ef = tk.Frame(card, bg=C['bg2']); ef.pack(fill=tk.X, pady=(4,0))
            v = tk.StringVar(value="0")
            e = tk.Entry(ef, textvariable=v, font=F['h2'], bg=C['bg'], fg=C['tx'], relief=tk.FLAT,
                         bd=0, width=8, highlightthickness=1, highlightbackground=C['brd2'],
                         highlightcolor=C['focus'], insertbackground=C['tx'],
                         selectbackground=C['sel'], selectforeground=C['self'])
            e.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
            e.bind('<Button-1>', _focus)
            if unit:
                tk.Label(ef, text=unit, font=F['cap'], bg=C['bg2'], fg=C['tx3']).pack(side=tk.RIGHT, padx=4)
            self.wv[key] = v
        tk.Button(pf, text="Save", command=self._save_wk, **_sbtn(pady=6)).grid(
            row=0, column=len(params), padx=(8,0), sticky=tk.E+tk.W)
        # Treeview
        tf = tk.Frame(t, bg=C['bg']); tf.pack(fill=tk.BOTH, expand=True, padx=16, pady=(4,8))
        cols = ("#","Date","From","To","Order nr","Price EUR","Full trip","PLN")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", height=12)
        ws = [36,95,130,130,100,85,90,85]
        for c, w in zip(cols, ws):
            self.tree.heading(c, text=c, command=lambda x=c: self._sort(x))
            self.tree.column(c, width=w, minwidth=36)
        sb = ttk.Scrollbar(tf, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.tag_configure("even", background=C['bg'])
        self.tree.tag_configure("odd", background=C['bg2'])
        self.tree.tag_configure("storno", foreground=C['err'])
        self.ctx = tk.Menu(self.tree, tearoff=0, font=F['body'])
        self.ctx.add_command(label="Edit order", command=self._edit_ord)
        self.ctx.add_command(label="Delete order", command=self._del_ord)
        self.ctx.add_separator()
        self.ctx.add_command(label="Move up", command=self._move_up)
        self.ctx.add_command(label="Move down", command=self._move_down)
        self.ctx.add_separator()
        self.ctx.add_command(label="Copy row", command=self._copy_row)
        self.tree.bind("<Button-2>" if sys.platform=="darwin" else "<Button-3>", self._ctx_show)
        self.tree.bind("<Double-1>", lambda e: self._edit_ord())
        # Summary cards
        sf = tk.Frame(t, bg=C['bg']); sf.pack(fill=tk.X, padx=16, pady=(0,8))
        self.sl = {}
        cards = [("SUMA EUR","suma_eur",C['okb'],C['okt']),
                 ("SUMA PO AUT","suma_po_aut_eur",C['okb'],C['okt']),
                 ("STAWKA /km","stawka_eur",C['infb'],C['inft']),
                 ("PO AUT /km","po_aut_eur",C['infb'],C['inft']),
                 ("SPALANIE","fuel_consumption",C['wrnb'],C['wrnt']),
                 ("AUTO DE EUR","auto_de_eur",C['wrnb'],C['wrnt'])]
        for i,(lbl,key,bg,fg) in enumerate(cards):
            card = tk.Frame(sf, bg=bg, padx=12, pady=8)
            card.grid(row=0, column=i, padx=3, sticky=tk.NSEW)
            sf.columnconfigure(i, weight=1)
            tk.Label(card, text=lbl, font=F['mlbl'], bg=bg, fg=fg).pack(anchor=tk.W)
            lb = tk.Label(card, text="—", font=F['metric'], bg=bg, fg=fg)
            lb.pack(anchor=tk.W, pady=(2,0))
            self.sl[key] = lb
        # Bottom
        bt = tk.Frame(t, bg=C['bg']); bt.pack(fill=tk.X, padx=16, pady=(0,12))
        tk.Button(bt, text="Export CSV", command=self._csv, **_sbtn()).pack(side=tk.LEFT, padx=(0,6))
        tk.Button(bt, text="Export JSON", command=self._json, **_sbtn()).pack(side=tk.LEFT, padx=(0,6))
        tk.Button(bt, text="Sort by date", command=self._sort_by_date, **_sbtn()).pack(side=tk.LEFT, padx=(0,6))
        tk.Button(bt, text="Print", command=self._print_table, **_sbtn()).pack(side=tk.LEFT)
        tk.Button(bt, text="Add order", command=self._add_ord, **_pbtn()).pack(side=tk.RIGHT)

    # ═══════ TAB 3: STATISTICS ═══════
    def _t3(self):
        t = self.t3
        tk.Button(t, text="Refresh statistics", command=self._ref_stats, **_sbtn()).pack(
            anchor=tk.W, padx=16, pady=(12,8))
        cf = tk.Frame(t, bg=C['bg']); cf.pack(fill=tk.X, padx=16, pady=(0,8))
        self.stl = {}
        for i,(k,ti) in enumerate([("total_orders","Total orders"),("unique_plates","Trucks"),
                                    ("total_fracht_eur","Total EUR"),("avg_fracht_eur","Avg EUR"),
                                    ("date_range","Date range")]):
            card = tk.Frame(cf, bg=C['bg2'], padx=14, pady=10,
                           highlightthickness=1, highlightbackground=C['brd'])
            card.grid(row=0, column=i, padx=4, sticky=tk.NSEW)
            cf.columnconfigure(i, weight=1)
            tk.Label(card, text=ti, font=F['mlbl'], bg=C['bg2'], fg=C['tx2']).pack(anchor=tk.W)
            lb = tk.Label(card, text="—", font=F['metric'], bg=C['bg2'], fg=C['tx'])
            lb.pack(anchor=tk.W, pady=(2,0))
            self.stl[k] = lb
        self.chf = tk.Frame(t, bg=C['bg'])
        self.chf.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0,12))

    def _tab(self, e):
        i = self.nb.index(self.nb.select())
        if i == 1: self._ref_db()
        elif i == 2: self._ref_stats()

    # ═══════ PROCESSING LOGIC ═══════
    def _browse(self):
        ini = self.current_folder if self.current_folder and os.path.exists(self.current_folder) else os.path.expanduser("~")
        f = filedialog.askdirectory(title="Select PDF Folder", initialdir=ini)
        if f:
            self.current_folder = f; self.folder_var.set(f); self._save_folder(f); self._scan()

    def _scan(self):
        if not self.current_folder: return
        try:
            n = len([f for f in os.listdir(self.current_folder) if f.lower().endswith('.pdf')])
            if n == 0:
                self.pdf_lbl.config(text="No PDFs found", fg=C['errt']); self.proc_btn.config(state=tk.DISABLED)
            else:
                self.pdf_lbl.config(text=f"{n} PDF{'s' if n!=1 else ''} found", fg=C['okt'])
                self.proc_btn.config(state=tk.NORMAL)
        except Exception as e: self._log(f"Scan error: {e}", "error")

    def _on_proc(self):
        if not self.current_folder: messagebox.showwarning("No folder","Select a folder first."); return
        ps = [f for f in os.listdir(self.current_folder) if f.lower().endswith('.pdf')]
        if not ps: messagebox.showwarning("No PDFs","No PDF files found."); return
        if not messagebox.askyesno("Confirm",f"Process {len(ps)} PDFs?"): return
        self.processing = True; self.stop_requested = False
        self.proc_btn.config(state=tk.DISABLED); self.stop_btn.config(state=tk.NORMAL)
        self.pbar.start(10)
        self.log_t.config(state=tk.NORMAL); self.log_t.delete(1.0, tk.END); self.log_t.config(state=tk.DISABLED)
        threading.Thread(target=self._proc_thread, daemon=True).start()

    def _stop(self):
        self.stop_requested = True; self._log("Stopping...","warning"); self.stop_btn.config(state=tk.DISABLED)

    def _proc_thread(self):
        try:
            self._log("Starting processing","info")
            rd = PDFReader(self.current_folder); pfs = rd.list_pdf_files()
            if not pfs: self._log("No PDFs found","error"); self._fin(None); return
            self._log(f"Found {len(pfs)} PDFs\n","info")
            res, ok, fail = [], 0, 0
            for i, pf in enumerate(pfs, 1):
                if self.stop_requested: self._log("Stopped by user","warning"); break
                self._log(f"[{i}/{len(pfs)}] {pf}","info")
                try:
                    txt = rd.extract_text(os.path.join(self.current_folder, pf))
                    d = self.regex_extractor.extract_all_fields(txt, verbose=False)
                    lc, uc = self.city_extractor.extract_from_text(txt)
                    d['miejsce_zaladunku']=lc; d['miejsce_rozladunku']=uc; d['source_file']=pf
                    ms = [k for k,v in d.items() if v is None and k!='source_file']
                    if ms: self._log(f"  Missing: {', '.join(ms)}","warning")
                    else: self._log("  Complete","success"); ok+=1
                    res.append(d)
                except Exception as e: self._log(f"  Error: {e}","error"); fail+=1
            if self.stop_requested: self._fin(None); return
            gr, nop = self.data_processor.group_by_plate(res)
            self._log(f"\n{len(gr)} plates, {len(nop)} without plate","info")
            self._log("\nSaving to database","info")
            dupes, saved = 0, 0
            for plate, orders in gr.items():
                tid, _ = self.db.add_truck(plate)
                for o in sorted(orders, key=lambda x: x.get('termin_rozladunku') or '9999'):
                    dt = o.get('termin_rozladunku','')
                    wid = self.db.find_or_create_week_table(tid, dt, DEFAULT_EUR_PLN_RATE)
                    s, m = self.db.add_order(wid, {'zlecenie_nr':o.get('zlecenie_nr'),
                        'termin_rozladunku':dt, 'miejsce_zaladunku':o.get('miejsce_zaladunku'),
                        'miejsce_rozladunku':o.get('miejsce_rozladunku'),
                        'fracht_eur':o.get('fracht'), 'source_file':o.get('source_file')})
                    if s: saved+=1; self._log(f"  Saved {o.get('zlecenie_nr','?')}","success")
                    elif m=="duplicate": dupes+=1; self._log(f"  Duplicate: {o.get('zlecenie_nr','?')}","warning")
                    else: self._log(f"  Failed: {o.get('zlecenie_nr','?')}: {m}","error")
            self._log(f"\nSaved: {saved} | Duplicates: {dupes} | Errors: {fail}","info")
            if self.sh_var.get():
                self._log("\nExporting to Google Sheets","info")
                try:
                    if not self.sheets_exporter:
                        self.sheets_exporter = GoogleSheetsExporter(GOOGLE_SHEET_ID, CREDENTIALS_FILE)
                    for pl, ords in gr.items():
                        for o in sorted(ords, key=lambda x: x.get('termin_rozladunku') or '9999'):
                            self.sheets_exporter.insert_order(pl, o)
                    self._log("Sheets export complete","success")
                except Exception as e: self._log(f"Sheets error: {e}","error")
            self._fin({'total':len(pfs),'saved':saved,'dupes':dupes,'failed':fail})
        except Exception as e: self._log(f"Fatal error: {e}","error"); self._fin(None)

    def _fin(self, r):
        self.processing = False; self.pbar.stop()
        self.proc_btn.config(state=tk.NORMAL); self.stop_btn.config(state=tk.DISABLED)
        if r:
            self.sum_lbl.config(
                text=f"{r['total']} PDFs processed  |  {r['saved']} saved  |  {r['dupes']} duplicates  |  {r['failed']} errors",
                fg=C['okt'] if r['failed']==0 else C['wrnt'])
        else: self.sum_lbl.config(text="Processing stopped or failed", fg=C['errt'])

    # ═══════ DB TAB LOGIC ═══════
    def _ref_db(self):
        ts = self.db.get_all_trucks(); ps = [t['plate'] for t in ts]
        menu = self.trk_menu['menu']; menu.delete(0, 'end')
        for plate in ps:
            menu.add_command(label=plate, font=F['body'], command=lambda p=plate: self.trk_var.set(p))
        if ps and self.trk_var.get() in ('Select truck...', ''): self.trk_var.set(ps[0])

    def _trk_sel(self, e):
        p = self.trk_var.get()
        if not p or p == 'Select truck...': return
        tr = self.db.get_truck_by_plate(p)
        if not tr: return
        wks = self.db.get_week_tables(tr['id']); ids = [w['week_identifier'] for w in wks]
        self._week_data = {w['week_identifier']: w for w in wks}
        menu = self.wk_menu['menu']; menu.delete(0, 'end')
        for wid in ids:
            menu.add_command(label=wid, font=F['body'], command=lambda w=wid: self.wk_var.set(w))
        if ids:
            # Try to find the week covering today's date
            from datetime import date
            today = date.today()
            best = ids[-1]  # fallback: last (most recent) week
            for wid_str in ids:
                parsed = self.db.parse_week_identifier(wid_str)
                if parsed:
                    wy, wm, ws, we = parsed
                    yr = wy if wy else today.year
                    if yr == today.year and wm == today.month and ws <= today.day <= we:
                        best = wid_str; break
            self.wk_var.set(best)
        else: self.wk_var.set(''); self._clr()

    def _wk_sel(self, e):
        wid = self.wk_var.get()
        if not wid or wid == 'Select week...' or wid not in self._week_data: return
        wt = self._week_data[wid]; self._current_wt_id = wt['id']
        for k, v in self.wv.items(): v.set(str(wt.get(k,0) or 0))
        self._load_ord(wt['id']); self._upd_sum(wt['id'])

    def _load_ord(self, wid):
        for i in self.tree.get_children(): self.tree.delete(i)
        ords = self.db.get_orders_by_week(wid)
        wt = self.db.get_week_table(wid); rate = wt['eur_pln_rate'] if wt else 4.25
        for i, o in enumerate(ords):
            fr = o['fracht_eur']
            pln = round(fr*rate,2) if fr else "—"
            cena = f"{fr:.2f}" if fr else ("storno?" if o['is_storno'] else "—")
            ftp = f"{o['full_trip_price']:.2f}" if o.get('full_trip_price') else ""
            tg = "storno" if o['is_storno'] else ("even" if i%2==0 else "odd")
            self.tree.insert("",tk.END,iid=str(o['id']),values=(
                o['row_number'], o['termin_rozladunku'] or "", o['miejsce_zaladunku'] or "",
                o['miejsce_rozladunku'] or "", o['zlecenie_nr'] or "", cena, ftp,
                pln if isinstance(pln,str) else f"{pln:.2f}"), tags=(tg,))

    def _upd_sum(self, wid):
        s = self.db.get_week_summary(wid)
        if not s: return
        for k, lb in self.sl.items():
            v = s.get(k,0); lb.config(text=f"{v:.2f}" if isinstance(v,(int,float)) else str(v))

    def _clr(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for lb in self.sl.values(): lb.config(text="—")

    def _save_wk(self):
        if not self._current_wt_id: return
        try:
            kw = {}
            for k, v in self.wv.items():
                try: kw[k] = float(v.get())
                except ValueError: kw[k] = 0
            self.db.update_week_table(self._current_wt_id, **kw)
            wt = self.db.get_week_table(self._current_wt_id)
            if wt: self._week_data[wt['week_identifier']] = wt
            self._upd_sum(self._current_wt_id)
            messagebox.showinfo("Saved","Week parameters updated.")
        except Exception as e: messagebox.showerror("Error",str(e))

    def _sort(self, col):
        items = [(self.tree.set(k,col),k) for k in self.tree.get_children("")]
        try: items.sort(key=lambda t: float(t[0]) if t[0].replace('.','',1).replace('-','',1).isdigit() else t[0])
        except: items.sort(key=lambda t: t[0])
        for idx,(_,k) in enumerate(items): self.tree.move(k,"",idx)

    def _ctx_show(self, e):
        it = self.tree.identify_row(e.y)
        if it: self.tree.selection_set(it); self.ctx.post(e.x_root,e.y_root)

    def _move_up(self):
        sel = self.tree.selection()
        if not sel or not self._current_wt_id: return
        oid = int(sel[0])
        ords = self.db.get_orders_by_week(self._current_wt_id)
        idx = next((i for i,o in enumerate(ords) if o['id']==oid), None)
        if idx is None or idx == 0: return
        # Swap row_numbers with the order above
        above = ords[idx-1]
        rn_cur, rn_above = ords[idx]['row_number'], above['row_number']
        self.db.update_order(oid, {'row_number': rn_above})
        self.db.update_order(above['id'], {'row_number': rn_cur})
        self._load_ord(self._current_wt_id)
        self.tree.selection_set(str(oid)); self.tree.see(str(oid))

    def _move_down(self):
        sel = self.tree.selection()
        if not sel or not self._current_wt_id: return
        oid = int(sel[0])
        ords = self.db.get_orders_by_week(self._current_wt_id)
        idx = next((i for i,o in enumerate(ords) if o['id']==oid), None)
        if idx is None or idx >= len(ords)-1: return
        # Swap row_numbers with the order below
        below = ords[idx+1]
        rn_cur, rn_below = ords[idx]['row_number'], below['row_number']
        self.db.update_order(oid, {'row_number': rn_below})
        self.db.update_order(below['id'], {'row_number': rn_cur})
        self._load_ord(self._current_wt_id)
        self.tree.selection_set(str(oid)); self.tree.see(str(oid))

    def _sort_by_date(self):
        if not self._current_wt_id: return
        ords = self.db.get_orders_by_week(self._current_wt_id)
        if not ords: return
        sorted_ords = sorted(ords, key=lambda o: o.get('termin_rozladunku') or '9999')
        for i, o in enumerate(sorted_ords, 1):
            if o['row_number'] != i:
                self.db.update_order(o['id'], {'row_number': i})
        self._load_ord(self._current_wt_id)

    def _print_table(self):
        if not self._current_wt_id: messagebox.showwarning("No data","Select a truck and week first."); return
        wt = self.db.get_week_table(self._current_wt_id)
        if not wt: return
        ords = self.db.get_orders_by_week(self._current_wt_id)
        sm = self.db.get_week_summary(self._current_wt_id)
        truck = self.db.conn.execute("SELECT plate FROM trucks WHERE id=?", (wt['truck_id'],)).fetchone()
        plate = truck['plate'] if truck else '?'
        rate = wt['eur_pln_rate'] or 4.25
        # Build order rows
        rows_html = ""
        for o in ords:
            fr = o['fracht_eur']
            cena = f"{fr:.2f}" if fr else ("storno" if o['is_storno'] else "—")
            pln = f"{fr*rate:.2f}" if fr else "—"
            ftp = f"{o['full_trip_price']:.2f}" if o.get('full_trip_price') else ""
            cls = ' class="storno"' if o['is_storno'] else ''
            rows_html += f"""<tr{cls}>
                <td>{o['row_number']}</td><td>{o['termin_rozladunku'] or ''}</td>
                <td>{o['miejsce_zaladunku'] or ''}</td><td>{o['miejsce_rozladunku'] or ''}</td>
                <td>{o['zlecenie_nr'] or ''}</td><td class="num">{cena}</td>
                <td class="num">{ftp}</td><td class="num">{pln}</td>
            </tr>\n"""
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{plate} — {wt['week_identifier']}</title>
<style>
  @page {{ margin: 15mm; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: 'SF Pro Display','Helvetica Neue','Segoe UI',sans-serif;
          font-size: 11pt; color: #212529; padding: 20px; }}
  h1 {{ font-size: 16pt; margin-bottom: 4px; }}
  .meta {{ color: #6C757D; font-size: 10pt; margin-bottom: 16px; }}
  .params {{ display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }}
  .param {{ background: #F8F9FA; border: 1px solid #E9ECEF; border-radius: 4px;
            padding: 8px 14px; min-width: 120px; }}
  .param .label {{ font-size: 9pt; color: #6C757D; }}
  .param .value {{ font-size: 13pt; font-weight: bold; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; }}
  th {{ background: #F1F3F5; color: #6C757D; font-size: 10pt; text-align: left;
       padding: 8px 10px; border-bottom: 2px solid #DEE2E6; }}
  td {{ padding: 7px 10px; border-bottom: 1px solid #E9ECEF; font-size: 10.5pt; }}
  tr:nth-child(even) {{ background: #F8F9FA; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .storno td {{ color: #FA5252; }}
  .summary {{ display: flex; gap: 10px; flex-wrap: wrap; }}
  .card {{ border-radius: 4px; padding: 10px 16px; min-width: 100px; }}
  .card .label {{ font-size: 9pt; }}
  .card .value {{ font-size: 16pt; font-weight: bold; }}
  .green {{ background: #EBFBEE; color: #2B8A3E; }}
  .blue {{ background: #E7F5FF; color: #1864AB; }}
  .orange {{ background: #FFF4E6; color: #D9480F; }}
  .footer {{ margin-top: 20px; font-size: 9pt; color: #ADB5BD; text-align: center; }}
  @media print {{
    body {{ padding: 0; }}
    .no-print {{ display: none; }}
  }}
</style>
</head><body>
<h1>{plate} — Week {wt['week_identifier']}</h1>
<p class="meta">Transport Extractor &mdash; agdar.it &mdash; Printed {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<div class="params">
  <div class="param"><div class="label">KM total</div><div class="value">{wt['km_total'] or 0} km</div></div>
  <div class="param"><div class="label">Fuel refueled</div><div class="value">{wt['fuel_refueled'] or 0} L</div></div>
  <div class="param"><div class="label">KM in Germany</div><div class="value">{wt['km_in_germany'] or 0} km</div></div>
  <div class="param"><div class="label">EUR/PLN rate</div><div class="value">{rate}</div></div>
  <div class="param"><div class="label">Extra highway</div><div class="value">{wt['extra_highway_charge_eur'] or 0} EUR</div></div>
</div>
<table>
<thead><tr><th>#</th><th>Date</th><th>From</th><th>To</th><th>Order nr</th>
<th class="num">Price EUR</th><th class="num">Full trip</th><th class="num">PLN</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>
<div class="summary">
  <div class="card green"><div class="label">SUMA EUR</div><div class="value">{sm.get('suma_eur',0):.2f}</div></div>
  <div class="card green"><div class="label">SUMA PO AUT</div><div class="value">{sm.get('suma_po_aut_eur',0):.2f}</div></div>
  <div class="card blue"><div class="label">STAWKA /km</div><div class="value">{sm.get('stawka_eur',0):.2f}</div></div>
  <div class="card blue"><div class="label">PO AUT /km</div><div class="value">{sm.get('po_aut_eur',0):.2f}</div></div>
  <div class="card orange"><div class="label">SPALANIE</div><div class="value">{sm.get('fuel_consumption',0):.2f}</div></div>
  <div class="card orange"><div class="label">AUTO DE EUR</div><div class="value">{sm.get('auto_de_eur',0):.2f}</div></div>
</div>
<p class="footer">{len(ords)} orders &bull; Generated by Transport Extractor</p>
<script>window.onload = function() {{ window.print(); }}</script>
</body></html>"""
        fd, path = tempfile.mkstemp(suffix='.html', prefix='transport_print_')
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(html)
        webbrowser.open('file://' + path)

    # ═══════ DIALOGS ═══════
    def _make_dlg(self, title, size="560x520"):
        dlg = tk.Toplevel(self.window); dlg.title(title); dlg.geometry(size)
        dlg.resizable(False, False); dlg.transient(self.window)
        dlg.configure(bg=C['bg']); _dlg_setup(dlg)
        return dlg

    def _make_field(self, parent, label, val="", width=30):
        f = tk.Frame(parent, bg=C['bg'], padx=20, pady=6); f.pack(fill=tk.X)
        tk.Label(f, text=label, font=F['sm'], bg=C['bg'], fg=C['tx2'], width=18, anchor=tk.W).pack(side=tk.LEFT)
        e = tk.Entry(f, font=F['body'], width=width, bg=C['bg'], fg=C['tx'], relief=tk.FLAT, bd=0,
                     insertbackground=C['tx'], highlightthickness=1, highlightbackground=C['brd2'],
                     highlightcolor=C['focus'], selectbackground=C['sel'], selectforeground=C['self'])
        e.insert(0, val); e.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=6)
        e.bind('<Button-1>', _focus)
        return e

    def _edit_ord(self):
        sel = self.tree.selection()
        if not sel: return
        oid = int(sel[0])
        ords = self.db.get_orders_by_week(self._current_wt_id)
        o = next((x for x in ords if x['id']==oid), None)
        if not o: return
        dlg = self._make_dlg(f"Edit order — {o.get('zlecenie_nr','')}")
        flds = [("Order number","zlecenie_nr"),("Unloading date","termin_rozladunku"),
                ("From (loading)","miejsce_zaladunku"),("To (unloading)","miejsce_rozladunku"),
                ("Price EUR","fracht_eur"),("Full trip price","full_trip_price"),("Source file","source_file")]
        ents = {}
        for lb, k in flds:
            ents[k] = self._make_field(dlg, lb, str(o.get(k) or ""))
        sv = tk.BooleanVar(value=bool(o.get('is_storno',0)))
        tk.Checkbutton(dlg, text="Storno", variable=sv, font=F['body'],
                       bg=C['bg'], fg=C['tx'], selectcolor=C['bg'], activebackground=C['bg']).pack(pady=8)
        def save():
            d = {}
            for k, e in ents.items():
                v = e.get().strip()
                if k in ('fracht_eur','full_trip_price'):
                    try: d[k] = float(v) if v else None
                    except: d[k] = None
                else: d[k] = v or None
            d['is_storno'] = int(sv.get())
            if self.db.update_order(oid, d):
                dlg.destroy(); self._load_ord(self._current_wt_id); self._upd_sum(self._current_wt_id)
            else: messagebox.showerror("Error","Update failed")
        bf = tk.Frame(dlg, bg=C['bg'], pady=12); bf.pack()
        tk.Button(bf, text="Save changes", command=save, **_pbtn()).pack(side=tk.LEFT, padx=8)
        tk.Button(bf, text="Cancel", command=dlg.destroy, **_sbtn()).pack(side=tk.LEFT, padx=8)
        list(ents.values())[0].focus_set(); dlg.update_idletasks()

    def _del_ord(self):
        sel = self.tree.selection()
        if not sel: return
        oid = int(sel[0]); vals = self.tree.item(sel[0],'values')
        nr = vals[4] if len(vals)>4 else "?"
        if messagebox.askyesno("Delete order",f"Delete order {nr}? This cannot be undone."):
            self.db.delete_order(oid); self._load_ord(self._current_wt_id); self._upd_sum(self._current_wt_id)

    def _copy_row(self):
        sel = self.tree.selection()
        if not sel: return
        vals = self.tree.item(sel[0],'values')
        self.window.clipboard_clear(); self.window.clipboard_append("\t".join(str(v) for v in vals))

    def _add_ord(self):
        if not self._current_wt_id: messagebox.showwarning("No week","Select a truck and week first."); return
        dlg = self._make_dlg("Add order", "560x480")
        flds = [("Order number","zlecenie_nr"),("Unloading date","termin_rozladunku"),
                ("From (loading)","miejsce_zaladunku"),("To (unloading)","miejsce_rozladunku"),
                ("Price EUR","fracht_eur"),("Full trip price","full_trip_price"),("Source file","source_file")]
        ents = {}
        for lb, k in flds: ents[k] = self._make_field(dlg, lb)
        def save():
            d = {}
            for k, e in ents.items():
                v = e.get().strip()
                if k in ('fracht_eur','full_trip_price'):
                    try: d[k] = float(v) if v else None
                    except: d[k] = None
                else: d[k] = v or None
            ok, msg = self.db.add_order(self._current_wt_id, d)
            if ok: dlg.destroy(); self._load_ord(self._current_wt_id); self._upd_sum(self._current_wt_id)
            else: messagebox.showerror("Error",f"Failed: {msg}")
        bf = tk.Frame(dlg, bg=C['bg'], pady=12); bf.pack()
        tk.Button(bf, text="Add order", command=save, **_pbtn()).pack(side=tk.LEFT, padx=8)
        tk.Button(bf, text="Cancel", command=dlg.destroy, **_sbtn()).pack(side=tk.LEFT, padx=8)
        list(ents.values())[0].focus_set(); dlg.update_idletasks()

    def _add_wk(self):
        p = self.trk_var.get()
        if not p or p == 'Select truck...': messagebox.showwarning("No truck","Select a truck first."); return
        tr = self.db.get_truck_by_plate(p)
        if not tr: return
        dlg = self._make_dlg("Add week table", "460x360")
        flds = [("Week ID (e.g. 02.02-09)","wid"),("KM total","km"),("Fuel refueled (L)","fuel"),
                ("KM in Germany","kmde"),("EUR/PLN rate","rate")]
        ents = {}
        for lb, k in flds:
            default = str(DEFAULT_EUR_PLN_RATE) if k=="rate" else ("" if k=="wid" else "0")
            ents[k] = self._make_field(dlg, lb, default, width=14)
        def save():
            wid = ents["wid"].get().strip()
            if not wid: messagebox.showwarning("Missing","Week ID is required."); return
            try:
                self.db.add_week_table(tr['id'], wid,
                    km_total=float(ents["km"].get() or 0), fuel_refueled=float(ents["fuel"].get() or 0),
                    km_in_germany=float(ents["kmde"].get() or 0), eur_pln_rate=float(ents["rate"].get() or 4.25))
                dlg.destroy(); self._trk_sel(None)
            except Exception as e: messagebox.showerror("Error",str(e))
        bf = tk.Frame(dlg, bg=C['bg'], pady=12); bf.pack()
        tk.Button(bf, text="Create week", command=save, **_pbtn()).pack(side=tk.LEFT, padx=8)
        tk.Button(bf, text="Cancel", command=dlg.destroy, **_sbtn()).pack(side=tk.LEFT, padx=8)
        list(ents.values())[0].focus_set(); dlg.update_idletasks()

    def _del_wk(self):
        if not self._current_wt_id: messagebox.showwarning("No week","Select a week first."); return
        wk = self.wk_var.get()
        if messagebox.askyesno("Delete week",f"Delete week '{wk}' and all its orders?"):
            self.db.delete_week_table(self._current_wt_id); self._current_wt_id = None; self._trk_sel(None)

    # ═══════ EXPORTS ═══════
    def _csv(self):
        if not self._current_wt_id: return
        fp = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if not fp: return
        ords = self.db.export_orders_for_csv(self._current_wt_id)
        try:
            with open(fp,'w',newline='',encoding='utf-8-sig') as f:
                w = csv.writer(f, delimiter=';')
                w.writerow(["#","Date","From","To","Order nr","Price EUR","PLN","File"])
                for o in ords:
                    fr = o.get('fracht_eur')
                    c = f"{fr:.2f}" if fr else ("storno?" if o.get('is_storno') else "")
                    w.writerow([o.get('row_number',''),o.get('termin_rozladunku',''),
                                o.get('miejsce_zaladunku',''),o.get('miejsce_rozladunku',''),
                                o.get('zlecenie_nr',''),c,o.get('price_pln',''),o.get('source_file','')])
            messagebox.showinfo("Exported",f"Saved to {fp}")
        except Exception as e: messagebox.showerror("Error",str(e))

    def _json(self):
        if not self._current_wt_id: return
        fp = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON","*.json")])
        if not fp: return
        ords = self.db.export_orders_for_csv(self._current_wt_id)
        sm = self.db.get_week_summary(self._current_wt_id)
        try:
            with open(fp,'w',encoding='utf-8') as f:
                json.dump({"summary":sm,"orders":ords},f,ensure_ascii=False,indent=2,default=str)
            messagebox.showinfo("Exported",f"Saved to {fp}")
        except Exception as e: messagebox.showerror("Error",str(e))

    # ═══════ STATISTICS ═══════
    def _ref_stats(self):
        st = self.db.get_statistics()
        self.stl["total_orders"].config(text=str(st.get("total_orders",0)))
        self.stl["unique_plates"].config(text=str(st.get("unique_plates",0)))
        self.stl["total_fracht_eur"].config(text=f"{st.get('total_fracht_eur',0):.2f}")
        self.stl["avg_fracht_eur"].config(text=f"{st.get('avg_fracht_eur',0):.2f}")
        dr = st.get("date_range",{})
        mn, mx = dr.get('min_date','—'), dr.get('max_date','—')
        self.stl["date_range"].config(text=f"{mn} to {mx}", font=F['sm'])
        for w in self.chf.winfo_children(): w.destroy()
        if HAS_MPL: self._charts(st)
        else: self._txt_stats(st)

    def _charts(self, st):
        fig = Figure(figsize=(10,4), dpi=90, facecolor=C['bg'])
        opm = st.get("orders_per_month",{})
        if opm:
            ax = fig.add_subplot(121); ax.set_facecolor(C['bg'])
            ax.bar(list(opm.keys()),list(opm.values()),color=C['acc'],edgecolor='none')
            ax.set_title("Orders per month",fontsize=12,color=C['tx']); ax.tick_params(axis='x',rotation=45,labelsize=9)
            ax.spines['top'].set_visible(False); ax.spines['right'].set_visible(False)
        fpp = st.get("fracht_per_plate",{})
        if fpp:
            ax2 = fig.add_subplot(122); ax2.set_facecolor(C['bg'])
            ax2.bar(list(fpp.keys()),[fpp[p]["total_fracht"] for p in fpp],color=C['ok'],edgecolor='none')
            ax2.set_title("Revenue per truck (EUR)",fontsize=12,color=C['tx']); ax2.tick_params(axis='x',rotation=45,labelsize=9)
            ax2.spines['top'].set_visible(False); ax2.spines['right'].set_visible(False)
        fig.tight_layout()
        cv = FigureCanvasTkAgg(fig, self.chf); cv.draw()
        cv.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _txt_stats(self, st):
        tx = scrolledtext.ScrolledText(self.chf, font=F['mono'], height=12, bg=C['bg'], fg=C['tx'],
                                        relief=tk.FLAT, highlightthickness=1, highlightbackground=C['brd2'])
        tx.pack(fill=tk.BOTH, expand=True)
        fpp = st.get("fracht_per_plate",{})
        tx.insert(tk.END,"REVENUE PER TRUCK\n"+"─"*40+"\n")
        for p, d in sorted(fpp.items()):
            tx.insert(tk.END,f"  {p}: {d['total_fracht']:.2f} EUR ({d['order_count']} orders)\n")
        opm = st.get("orders_per_month",{})
        tx.insert(tk.END,f"\nORDERS PER MONTH\n"+"─"*40+"\n")
        for m, c in opm.items(): tx.insert(tk.END,f"  {m}: {c}\n")
        tx.config(state=tk.DISABLED)

    # ═══════ HELPERS ═══════
    def _log(self, msg, tag=""):
        self.log_t.config(state=tk.NORMAL)
        if tag: self.log_t.insert(tk.END, msg+"\n", tag)
        else: self.log_t.insert(tk.END, msg+"\n")
        self.log_t.see(tk.END); self.log_t.config(state=tk.DISABLED)
        self.window.update_idletasks()

    def _open_sheets(self):
        import webbrowser; webbrowser.open(f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}")

    def _check_creds(self):
        if not Path(CREDENTIALS_FILE).exists(): self.sh_var.set(False); self.sh_cb.config(state=tk.DISABLED)

    def _load_folder(self):
        p = Path("gui_config.json")
        if p.exists():
            try:
                with open(p) as f: return json.load(f).get('last_folder')
            except: pass
        return None

    def _save_folder(self, folder):
        try:
            with open("gui_config.json",'w') as f: json.dump({'last_folder':folder},f)
        except: pass

    def run(self): self.window.mainloop()

def main():
    app = TransportGUI(); app.run()

if __name__ == "__main__":
    main()