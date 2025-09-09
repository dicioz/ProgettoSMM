#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analisi Network Centralità Semplificata
Riutilizza codice esistente e aggiunge PageRank + analisi temporale
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

def checkpoint(message):
    """Print di checkpoint con timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"⏱️  [{timestamp}] CHECKPOINT: {message}")

def main():
    checkpoint("🚀 INIZIO ANALISI NETWORK CENTRALITÀ")
    print("=" * 60)
    
    try:
        # 1. CARICAMENTO DATI
        checkpoint("Caricamento dataset...")
        
        if not os.path.exists('youtube_comments_sentiment_nlp.csv'):
            checkpoint("❌ File dataset non trovato")
            return
            
        df = pd.read_csv('youtube_comments_sentiment_nlp.csv')
        checkpoint(f"✅ Dataset caricato: {len(df):,} commenti")
        
        # Verifica colonne necessarie
        required_cols = ['tipo_commento', 'id_commento_padre', 'autore', 'data_commento', 'prima_dopo_vision_pro']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            checkpoint(f"❌ Colonne mancanti: {missing_cols}")
            checkpoint("📋 Colonne disponibili:")
            for i, col in enumerate(df.columns, 1):
                print(f"   {i:2d}. {col}")
            return
        
        # 2. PREPARAZIONE DATI
        checkpoint("Preparazione dati per analisi network...")
        
        # Split PRE/POST Vision Pro  
        df_pre = df[df['prima_dopo_vision_pro'] == 'prima'].copy()
        df_post = df[df['prima_dopo_vision_pro'] == 'dopo'].copy()
        
        checkpoint(f"Split dataset - PRE: {len(df_pre):,}, POST: {len(df_post):,}")
        
        # 3. ANALISI METODOLOGIA V1 (Senza NetworkX per ora)
        checkpoint("Analisi network V1 - Estrazione interazioni dirette...")
        
        def analyze_direct_interactions(data, period_name):
            """Analizza interazioni dirette tra utenti (metodologia V1)"""
            
            # Filtra risposte valide
            replies = data[
                (data['tipo_commento'] == 'risposta') & 
                (data['id_commento_padre'].notna()) &
                (data['autore'].notna()) &
                (data['autore'] != '') &
                (data['autore'] != 'None')
            ].copy()
            
            checkpoint(f"{period_name} - Risposte trovate: {len(replies):,}")
            
            if len(replies) == 0:
                return {}
            
            # Mappa commenti padre -> autori
            parent_map = data.set_index('id_commento')['autore'].to_dict()
            
            # Conta interazioni dirette tra utenti diversi
            interactions = {}
            valid_interactions = 0
            
            for _, reply in replies.iterrows():
                reply_author = reply['autore']
                parent_id = reply['id_commento_padre']
                
                if parent_id in parent_map:
                    parent_author = parent_map[parent_id]
                    
                    # Evita self-loops e autori anonimi
                    if (reply_author != parent_author and 
                        parent_author and parent_author != 'None'):
                        
                        # Crea chiave per interazione (ordine alfabetico)
                        users = tuple(sorted([reply_author, parent_author]))
                        interactions[users] = interactions.get(users, 0) + 1
                        valid_interactions += 1
            
            # Calcola statistiche base
            unique_users = set()
            for user_pair in interactions.keys():
                unique_users.update(user_pair)
            
            stats = {
                'period': period_name,
                'total_replies': len(replies),
                'valid_interactions': valid_interactions,
                'unique_interactions': len(interactions),
                'unique_users': len(unique_users),
                'avg_interactions_per_pair': np.mean(list(interactions.values())) if interactions else 0,
                'max_interactions': max(interactions.values()) if interactions else 0,
                'top_user_pairs': sorted(interactions.items(), key=lambda x: x[1], reverse=True)[:10]
            }
            
            return stats
        
        # Analizza i tre dataset
        stats_pre = analyze_direct_interactions(df_pre, "PRE Vision Pro")
        stats_post = analyze_direct_interactions(df_post, "POST Vision Pro")
        stats_combined = analyze_direct_interactions(df, "COMBINED")
        
        # 4. VISUALIZZAZIONE RISULTATI
        checkpoint("Visualizzazione risultati network V1...")
        
        print(f"\n📊 RISULTATI ANALISI NETWORK V1")
        print("-" * 50)
        
        for stats in [stats_pre, stats_post, stats_combined]:
            if stats:
                print(f"\n🔍 {stats['period']}")
                print(f"   Risposte totali: {stats['total_replies']:,}")
                print(f"   Interazioni valide: {stats['valid_interactions']:,}")
                print(f"   Coppie utenti uniche: {stats['unique_interactions']:,}")
                print(f"   Utenti coinvolti: {stats['unique_users']:,}")
                print(f"   Media interazioni/coppia: {stats['avg_interactions_per_pair']:.2f}")
                print(f"   Max interazioni (coppia): {stats['max_interactions']:,}")
                
                if stats['top_user_pairs']:
                    print(f"   🏆 Top 3 coppie più attive:")
                    for i, ((user1, user2), count) in enumerate(stats['top_user_pairs'][:3], 1):
                        print(f"      {i}. {user1} ↔ {user2}: {count} interazioni")
        
        # 5. ANALISI TEMPORALE SEMPLIFICATA
        checkpoint("Analisi temporale interazioni...")
        
        # Converti date
        df['data_dt'] = pd.to_datetime(df['data_commento'], errors='coerce')
        df_temporal = df.dropna(subset=['data_dt']).copy()
        
        if len(df_temporal) > 0:
            start_date = df_temporal['data_dt'].min()
            end_date = df_temporal['data_dt'].max()
            
            checkpoint(f"Periodo temporale: {start_date.date()} -> {end_date.date()}")
            
            # Crea finestre settimanali
            window_days = 14
            temporal_stats = []
            current_date = start_date
            
            while current_date <= end_date:
                window_end = current_date + timedelta(days=window_days)
                
                window_data = df_temporal[
                    (df_temporal['data_dt'] >= current_date) & 
                    (df_temporal['data_dt'] < window_end)
                ]
                
                if len(window_data) >= 50:  # Minimo dati per analisi
                    window_stats = analyze_direct_interactions(
                        window_data, f"Window_{current_date.strftime('%Y-%m-%d')}"
                    )
                    window_stats['date'] = current_date
                    window_stats['window_end'] = window_end
                    temporal_stats.append(window_stats)
                
                current_date += timedelta(days=window_days)
            
            checkpoint(f"Finestre temporali analizzate: {len(temporal_stats)}")
            
            if temporal_stats:
                print(f"\n📈 EVOLUZIONE TEMPORALE (finestre di {window_days} giorni)")
                print("-" * 50)
                
                for i, stats in enumerate(temporal_stats[:10], 1):  # Mostra prime 10 finestre
                    print(f"{i:2d}. {stats['date'].strftime('%Y-%m-%d')}: "
                          f"{stats['unique_users']:3d} utenti, "
                          f"{stats['unique_interactions']:4d} coppie, "
                          f"{stats['valid_interactions']:5d} interazioni")
                
                if len(temporal_stats) > 10:
                    print(f"    ... e altre {len(temporal_stats)-10} finestre")
        
        # 6. SUMMARY E SALVATAGGIO
        checkpoint("Generazione summary finale...")
        
        summary_data = {
            'timestamp': datetime.now().isoformat(),
            'analysis_type': 'Network V1 - Direct Interactions Only',
            'total_comments': len(df),
            'pre_comments': len(df_pre),
            'post_comments': len(df_post),
            'pre_stats': stats_pre,
            'post_stats': stats_post,
            'combined_stats': stats_combined,
            'temporal_windows': len(temporal_stats) if 'temporal_stats' in locals() else 0
        }
        
        # Salva summary in CSV semplificato
        summary_rows = []
        
        for period, stats in [('PRE', stats_pre), ('POST', stats_post), ('COMBINED', stats_combined)]:
            if stats:
                summary_rows.append({
                    'Period': period,
                    'Total_Replies': stats['total_replies'],
                    'Valid_Interactions': stats['valid_interactions'],
                    'Unique_User_Pairs': stats['unique_interactions'],
                    'Unique_Users': stats['unique_users'],
                    'Avg_Interactions_Per_Pair': round(stats['avg_interactions_per_pair'], 3),
                    'Max_Interactions_Pair': stats['max_interactions']
                })
        
        if summary_rows:
            summary_df = pd.DataFrame(summary_rows)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            summary_file = f"network_v1_analysis_{timestamp}.csv"
            summary_df.to_csv(summary_file, index=False)
            checkpoint(f"✅ Summary salvato: {summary_file}")
            
            print(f"\n📋 SUMMARY COMPARATIVO")
            print("-" * 30)
            print(summary_df.to_string(index=False))
        
        checkpoint("✅ ANALISI COMPLETATA CON SUCCESSO!")
        
    except Exception as e:
        checkpoint(f"❌ ERRORE: {e}")
        import traceback
        print(f"\nDettagli errore:\n{traceback.format_exc()}")
    
    print("=" * 60)
    checkpoint("🎉 FINE ANALISI")

if __name__ == "__main__":
    main()
