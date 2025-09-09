#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analisi Network con Centralità Temporale - NetworkX
Obiettivi: Costruzione grafo V1, calcolo centralità e analisi temporale delle metriche
"""

import pandas as pd
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import warnings
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import signal

warnings.filterwarnings('ignore')

class NetworkAnalyzer:
    """Classe per analisi network robusta con gestione timeout e checkpoint"""
    
    def __init__(self, timeout_seconds=300):
        self.timeout = timeout_seconds
        self.results = {}
        
    def checkpoint(self, message):
        """Print di checkpoint con timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"⏱️  [{timestamp}] CHECKPOINT: {message}")
        
    def safe_execute(self, func, *args, **kwargs):
        """Esecuzione sicura con timeout"""
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *args, **kwargs)
                return future.result(timeout=self.timeout)
        except TimeoutError:
            self.checkpoint(f"⚠️  TIMEOUT ({self.timeout}s) per {func.__name__}")
            return None
        except Exception as e:
            self.checkpoint(f"❌ ERRORE in {func.__name__}: {str(e)[:100]}...")
            return None
    
    def create_user_network_v1(self, df, period_name="Dataset"):
        """
        Costruisce grafo utenti V1 - evita clique artificiali
        Metodologia: solo risposte dirette tra utenti diversi
        """
        self.checkpoint(f"Costruzione grafo V1 per {period_name}")
        
        try:
            G = nx.Graph()
            
            # Filtra solo risposte dirette tra utenti diversi
            replies = df[
                (df['tipo_commento'] == 'risposta') & 
                (df['id_commento_padre'].notna()) &
                (df['autore'].notna())
            ].copy()
            
            self.checkpoint(f"Risposte trovate: {len(replies):,}")
            
            # Mappa commenti padre -> autori
            parent_authors = df.set_index('id_commento')['autore'].to_dict()
            
            # Costruisci archi solo tra utenti diversi
            edges_added = 0
            for _, reply in replies.iterrows():
                reply_author = reply['autore']
                parent_id = reply['id_commento_padre']
                
                if parent_id in parent_authors:
                    parent_author = parent_authors[parent_id]
                    
                    # Evita self-loops e utenti anonimi
                    if (reply_author != parent_author and 
                        reply_author and parent_author and
                        reply_author != 'None' and parent_author != 'None'):
                        
                        if G.has_edge(reply_author, parent_author):
                            G[reply_author][parent_author]['weight'] += 1
                        else:
                            G.add_edge(reply_author, parent_author, weight=1)
                            edges_added += 1
            
            self.checkpoint(f"Grafo {period_name}: {G.number_of_nodes()} nodi, {G.number_of_edges()} archi")
            return G
            
        except Exception as e:
            self.checkpoint(f"❌ Errore costruzione grafo: {e}")
            return nx.Graph()
    
    def calculate_centralities_robust(self, G, network_name):
        """Calcola tutte le centralità con gestione robusta"""
        self.checkpoint(f"Calcolo centralità per {network_name}")
        
        if G.number_of_nodes() == 0:
            self.checkpoint("⚠️  Grafo vuoto, skip centralità")
            return {}
        
        results = {
            'network_name': network_name,
            'nodes': G.number_of_nodes(),
            'edges': G.number_of_edges(),
            'density': nx.density(G) if G.number_of_nodes() > 1 else 0
        }
        
        try:
            # 1. Degree Centrality (veloce)
            self.checkpoint("Calcolo Degree Centrality...")
            degree_cent = self.safe_execute(nx.degree_centrality, G)
            if degree_cent:
                results['degree_centrality'] = degree_cent
                results['avg_degree_centrality'] = np.mean(list(degree_cent.values()))
                results['top_degree'] = sorted(degree_cent.items(), key=lambda x: x[1], reverse=True)[:10]
            
            # 2. PageRank Centrality
            self.checkpoint("Calcolo PageRank Centrality...")
            pagerank_cent = self.safe_execute(nx.pagerank, G, max_iter=100, tol=1e-4)
            if pagerank_cent:
                results['pagerank_centrality'] = pagerank_cent  
                results['avg_pagerank_centrality'] = np.mean(list(pagerank_cent.values()))
                results['top_pagerank'] = sorted(pagerank_cent.items(), key=lambda x: x[1], reverse=True)[:10]
            
            # 3. Betweenness Centrality (più lenta - usa campionamento per grafi grandi)
            self.checkpoint("Calcolo Betweenness Centrality...")
            if G.number_of_nodes() > 1000:
                # Campionamento per grafi grandi
                k_sample = min(500, G.number_of_nodes())
                betweenness_cent = self.safe_execute(nx.betweenness_centrality, G, k=k_sample)
            else:
                betweenness_cent = self.safe_execute(nx.betweenness_centrality, G)
                
            if betweenness_cent:
                results['betweenness_centrality'] = betweenness_cent
                results['avg_betweenness_centrality'] = np.mean(list(betweenness_cent.values()))
                results['top_betweenness'] = sorted(betweenness_cent.items(), key=lambda x: x[1], reverse=True)[:10]
            
            self.checkpoint(f"✅ Centralità completate per {network_name}")
            return results
            
        except Exception as e:
            self.checkpoint(f"❌ Errore nel calcolo centralità: {e}")
            return results
    
    def create_temporal_centrality_graph(self, df, time_window_days=7):
        """Crea grafo temporale delle metriche di centralità (non basato su utenti)"""
        self.checkpoint("Creazione grafo temporale centralità")
        
        try:
            # Converti date
            df['data_dt'] = pd.to_datetime(df['data_commento'], errors='coerce')
            df_clean = df.dropna(subset=['data_dt']).copy()
            
            # Crea finestre temporali
            start_date = df_clean['data_dt'].min()
            end_date = df_clean['data_dt'].max()
            
            self.checkpoint(f"Periodo analisi: {start_date.date()} -> {end_date.date()}")
            
            # Genera finestre temporali
            temporal_results = []
            current_date = start_date
            
            while current_date <= end_date:
                window_end = current_date + timedelta(days=time_window_days)
                
                # Filtra dati per finestra temporale
                window_data = df_clean[
                    (df_clean['data_dt'] >= current_date) & 
                    (df_clean['data_dt'] < window_end)
                ]
                
                if len(window_data) >= 10:  # Minimo dati per analisi
                    self.checkpoint(f"Finestra {current_date.date()}: {len(window_data)} commenti")
                    
                    # Costruisci grafo per questa finestra
                    G_window = self.create_user_network_v1(window_data, f"Window_{current_date.date()}")
                    
                    if G_window.number_of_nodes() >= 3:
                        # Calcola centralità
                        metrics = self.calculate_centralities_robust(G_window, f"Temporal_{current_date.date()}")
                        
                        # Aggiungi timestamp
                        metrics['date'] = current_date
                        metrics['window_days'] = time_window_days
                        temporal_results.append(metrics)
                
                current_date += timedelta(days=time_window_days)
            
            self.checkpoint(f"Finestre temporali analizzate: {len(temporal_results)}")
            return temporal_results
            
        except Exception as e:
            self.checkpoint(f"❌ Errore analisi temporale: {e}")
            return []
    
    def plot_temporal_centralities(self, temporal_results, save_path=None):
        """Visualizza evoluzione temporale delle centralità medie"""
        self.checkpoint("Creazione grafici temporali centralità")
        
        if not temporal_results:
            self.checkpoint("⚠️  Nessun dato temporale per visualizzazione")
            return
        
        try:
            # Estrai dati temporali
            dates = [r['date'] for r in temporal_results]
            
            degree_means = [r.get('avg_degree_centrality', 0) for r in temporal_results]
            pagerank_means = [r.get('avg_pagerank_centrality', 0) for r in temporal_results] 
            betweenness_means = [r.get('avg_betweenness_centrality', 0) for r in temporal_results]
            
            # Crea grafico
            fig, axes = plt.subplots(3, 1, figsize=(14, 12))
            fig.suptitle('Evoluzione Temporale delle Centralità Medie\nApple Vision Pro - Analisi Network', 
                        fontsize=16, fontweight='bold')
            
            # Degree Centrality
            axes[0].plot(dates, degree_means, 'b-o', linewidth=2, markersize=4)
            axes[0].set_title('Degree Centrality Media nel Tempo')
            axes[0].set_ylabel('Degree Centrality Media')
            axes[0].grid(True, alpha=0.3)
            axes[0].tick_params(axis='x', rotation=45)
            
            # PageRank Centrality
            axes[1].plot(dates, pagerank_means, 'g-s', linewidth=2, markersize=4)
            axes[1].set_title('PageRank Centrality Media nel Tempo')
            axes[1].set_ylabel('PageRank Media')
            axes[1].grid(True, alpha=0.3)
            axes[1].tick_params(axis='x', rotation=45)
            
            # Betweenness Centrality
            axes[2].plot(dates, betweenness_means, 'r-^', linewidth=2, markersize=4)
            axes[2].set_title('Betweenness Centrality Media nel Tempo')
            axes[2].set_ylabel('Betweenness Media')
            axes[2].set_xlabel('Data')
            axes[2].grid(True, alpha=0.3)
            axes[2].tick_params(axis='x', rotation=45)
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                self.checkpoint(f"Grafico salvato: {save_path}")
            
            plt.show()
            
        except Exception as e:
            self.checkpoint(f"❌ Errore visualizzazione: {e}")


def main():
    """Funzione principale"""
    analyzer = NetworkAnalyzer(timeout_seconds=300)
    
    analyzer.checkpoint("🚀 INIZIO ANALISI NETWORK CENTRALITÀ TEMPORALE")
    print("=" * 70)
    
    try:
        # 1. CARICAMENTO DATI
        analyzer.checkpoint("Caricamento dataset...")
        df = pd.read_csv('youtube_comments_sentiment_nlp.csv')
        analyzer.checkpoint(f"Dataset caricato: {len(df):,} commenti")
        
        # Verifica presenza colonne necessarie
        required_cols = ['tipo_commento', 'id_commento_padre', 'autore', 'data_commento']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            analyzer.checkpoint(f"❌ Colonne mancanti: {missing_cols}")
            return
        
        # 2. COSTRUZIONE GRAFI V1
        analyzer.checkpoint("Costruzione grafi principali...")
        
        # Split PRE/POST Vision Pro
        df_pre = df[df['prima_dopo_vision_pro'] == 'prima'].copy()
        df_post = df[df['prima_dopo_vision_pro'] == 'dopo'].copy()
        
        analyzer.checkpoint(f"Split dataset - PRE: {len(df_pre):,}, POST: {len(df_post):,}")
        
        # Costruisci grafi
        G_pre = analyzer.create_user_network_v1(df_pre, "PRE Vision Pro")
        G_post = analyzer.create_user_network_v1(df_post, "POST Vision Pro")  
        G_combined = analyzer.create_user_network_v1(df, "COMBINED")
        
        # 3. CALCOLO CENTRALITÀ
        analyzer.checkpoint("Calcolo centralità per tutti i grafi...")
        
        metrics_pre = analyzer.calculate_centralities_robust(G_pre, "PRE Vision Pro")
        metrics_post = analyzer.calculate_centralities_robust(G_post, "POST Vision Pro")
        metrics_combined = analyzer.calculate_centralities_robust(G_combined, "COMBINED")
        
        # 4. VISUALIZZAZIONE RISULTATI CENTRALITÀ
        analyzer.checkpoint("Visualizzazione risultati centralità...")
        
        print(f"\n📊 RISULTATI CENTRALITÀ")
        print("-" * 50)
        
        for metrics in [metrics_pre, metrics_post, metrics_combined]:
            if metrics:
                name = metrics['network_name']
                print(f"\n🔍 {name}")
                print(f"   Nodi: {metrics['nodes']:,}")
                print(f"   Archi: {metrics['edges']:,}")
                print(f"   Densità: {metrics['density']:.6f}")
                
                if 'avg_degree_centrality' in metrics:
                    print(f"   Degree Centrality Media: {metrics['avg_degree_centrality']:.6f}")
                if 'avg_pagerank_centrality' in metrics:
                    print(f"   PageRank Media: {metrics['avg_pagerank_centrality']:.6f}")
                if 'avg_betweenness_centrality' in metrics:
                    print(f"   Betweenness Media: {metrics['avg_betweenness_centrality']:.6f}")
                
                # Top utenti per degree
                if 'top_degree' in metrics:
                    print(f"   🏆 Top 3 Degree:")
                    for i, (user, score) in enumerate(metrics['top_degree'][:3], 1):
                        print(f"      {i}. {user}: {score:.6f}")
        
        # 5. ANALISI TEMPORALE
        analyzer.checkpoint("Analisi temporale centralità...")
        
        temporal_results = analyzer.create_temporal_centrality_graph(df, time_window_days=14)
        
        if temporal_results:
            analyzer.checkpoint(f"Analisi temporale completata: {len(temporal_results)} finestre")
            
            # Crea visualizzazioni temporali
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            plot_path = f"temporal_centralities_{timestamp}.png"
            analyzer.plot_temporal_centralities(temporal_results, plot_path)
            
            # Salva risultati temporali
            temporal_df = pd.DataFrame(temporal_results)
            temporal_file = f"temporal_centralities_{timestamp}.csv"
            temporal_df.to_csv(temporal_file, index=False)
            analyzer.checkpoint(f"Risultati temporali salvati: {temporal_file}")
        
        # 6. SUMMARY FINALE
        analyzer.checkpoint("Generazione summary finale...")
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_comments': len(df),
            'pre_comments': len(df_pre),
            'post_comments': len(df_post),
            'networks': {
                'pre': {
                    'nodes': G_pre.number_of_nodes(),
                    'edges': G_pre.number_of_edges(),
                    'density': nx.density(G_pre) if G_pre.number_of_nodes() > 1 else 0
                },
                'post': {
                    'nodes': G_post.number_of_nodes(), 
                    'edges': G_post.number_of_edges(),
                    'density': nx.density(G_post) if G_post.number_of_nodes() > 1 else 0
                },
                'combined': {
                    'nodes': G_combined.number_of_nodes(),
                    'edges': G_combined.number_of_edges(),
                    'density': nx.density(G_combined) if G_combined.number_of_nodes() > 1 else 0
                }
            },
            'temporal_windows': len(temporal_results) if temporal_results else 0
        }
        
        # Salva summary
        summary_file = f"network_analysis_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        import json
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        analyzer.checkpoint(f"✅ ANALISI COMPLETATA! Summary: {summary_file}")
        
    except Exception as e:
        analyzer.checkpoint(f"❌ ERRORE GENERALE: {e}")
        
    print("=" * 70)
    analyzer.checkpoint("🎉 FINE ANALISI NETWORK CENTRALITÀ TEMPORALE")


if __name__ == "__main__":
    main()
