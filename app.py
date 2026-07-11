import streamlit as st
import pandas as pd
import h5py
import tempfile
import plotly.express as px
import os

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="VSD & Pump Dashboard", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. DAFTAR PARAMETER (MASTER LIST) ---
DESIRED_COLUMNS = [
    'time', 'DHDischargePressure', 'DHDischargeTemperature', 'DHDifferentialPressure', 
    'DHIntakePressure', 'DHIntakeTemp', 'DHMotorTemp', 'DHMotorYpoint', 
    'DHVibration', 'DHVibrationAX1', 'DHVibrationAY1', 'DHVibrationAZ1', 'DHVibrationY', 'DHVibrationZ', 
    'DH Cf', 'DH Cz', 'VsdFreqOut', 'VsdAmps', 'VsdMotAmps', 'VSD Power In', 'VSD Power Out', 
    'VSD Volts In', 'VSD Volts Out', 'VSD Torque Percentage Live', 'VSDG7 Load', 'VSDG7 Speed Cmd WR', 
    'Motor Load', 'Starts', 'Temperature', 'SupplyVolts', 'Drive Run Status', 'COS PHI Live',
    'Active Current Leakage', 'Passive Current Leakage'
]

# --- 3. SIDEBAR (PANEL KIRI) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2933/2933116.png", width=80) 
    st.title("⚙️ Control Panel")
    st.write("Silakan unggah log data sumur di sini.")
    uploaded_file = st.file_uploader("Upload File .h5", type=['h5', 'hdf5'])

# --- 4. TAMPILAN UTAMA ---
st.title("📊 H5 Converter")
st.markdown("---")

tab1, tab2 = st.tabs(["📈 Analisis Grafik Interaktif", "🗃️ Data Tabel & Download"])

if uploaded_file is not None:
    with st.spinner("Mengekstrak, mengonversi satuan, dan memproses data... ⏳"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".h5") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        dfs = []
        try:
            with h5py.File(tmp_path, 'r') as f:
                ts_group = f.get('Non-Conforming Time Series')
                if ts_group:
                    for tag_name in ts_group.keys():
                        if tag_name in DESIRED_COLUMNS:
                            dataset = ts_group[tag_name]
                            if len(dataset) > 0:
                                data = dataset[:]
                                if 'time' in data.dtype.names and 'value' in data.dtype.names:
                                    df = pd.DataFrame(data)
                                    
                                    # --- LOGIKA KONVERSI SATUAN ---
                                    if "Pressure" in tag_name:
                                        # Konversi Pascal ke PSI
                                        df['value'] = df['value'] * 0.0001450377
                                        tag_name = tag_name + " (PSI)"
                                    elif "Temp" in tag_name or "Temperature" in tag_name:
                                        # Konversi Kelvin ke Fahrenheit
                                        df['value'] = (df['value'] - 273.15) * 9/5 + 32
                                        tag_name = tag_name + " (°F)"
                                    # ------------------------------
                                    
                                    df = df.rename(columns={'value': tag_name})
                                    df['time'] = pd.to_datetime(df['time'], unit='s')
                                    dfs.append(df)
            
            if dfs:
                merged_df = dfs[0]
                for df in dfs[1:]:
                    merged_df = pd.merge(merged_df, df, on='time', how='outer')
                
                merged_df = merged_df.sort_values('time').reset_index(drop=True)
                
                # --- LOGIKA PENANGANAN KOLOM KOSONG ---
                for col in DESIRED_COLUMNS:
                    if col == 'time': continue
                    target_col = col
                    if "Pressure" in col:
                        target_col = col + " (PSI)"
                    elif "Temp" in col or "Temperature" in col:
                        target_col = col + " (°F)" # Diperbarui ke Fahrenheit
                        
                    if target_col not in merged_df.columns:
                        merged_df[target_col] = pd.NA
                
                merged_df = merged_df.ffill().bfill()
                
                # --- ISI DARI TAB 1 (GRAFIK) ---
                with tab1:
                    with st.expander("🔍 Klik untuk melihat Ringkasan Nilai Maksimum (Opsional)", expanded=False):
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            max_freq = merged_df['VsdFreqOut'].max() if 'VsdFreqOut' in merged_df.columns and pd.notna(merged_df['VsdFreqOut'].max()) else 0
                            st.metric(label="Max Frequency", value=f"{max_freq:.2f} Hz")
                        with col2:
                            max_amp = merged_df['VsdAmps'].max() if 'VsdAmps' in merged_df.columns and pd.notna(merged_df['VsdAmps'].max()) else 0
                            st.metric(label="Max VSD Amps", value=f"{max_amp:.2f} A")
                        with col3:
                            max_volt = merged_df['VSD Volts Out'].max() if 'VSD Volts Out' in merged_df.columns and pd.notna(merged_df['VSD Volts Out'].max()) else 0
                            st.metric(label="Max Volts Out", value=f"{max_volt:.2f} V")
                        with col4:
                            max_leak = merged_df['Active Current Leakage'].max() if 'Active Current Leakage' in merged_df.columns and pd.notna(merged_df['Active Current Leakage'].max()) else 0
                            st.metric(label="Max Active Leakage", value=f"{max_leak:.2f} mA")
                    
                    st.write("") 
                    
                    mode_persentase = st.toggle("⚖️ Tampilkan Grafik dalam Skala Persentase (0-100%)", value=False, 
                                                help="Aktifkan ini untuk membandingkan parameter yang nilainya jauh berbeda (misal: Frekuensi vs Tekanan).")
                    
                    parameter_pilihan = st.multiselect(
                        "Pilih parameter untuk di-plot (Bisa lebih dari 1):",
                        options=[col for col in merged_df.columns if col != 'time'],
                        default=['VsdFreqOut', 'VsdAmps'] if 'VsdFreqOut' in merged_df.columns else []
                    )
                    
                    if parameter_pilihan:
                        df_plot = merged_df[['time'] + parameter_pilihan].copy()
                        
                        if mode_persentase:
                            for col in parameter_pilihan:
                                max_val = df_plot[col].max()
                                if pd.notna(max_val) and max_val != 0:
                                    df_plot[col] = (df_plot[col] / max_val) * 100
                                else:
                                    df_plot[col] = 0
                            
                            y_label = "Persentase dari Nilai Maksimum (%)"
                        else:
                            y_label = "Nilai Parameter"

                        fig = px.line(df_plot, x='time', y=parameter_pilihan, 
                                      template="plotly_dark", 
                                      labels={"value": y_label, "time": "Waktu"})
                        fig.update_layout(legend_title_text='Parameter', hovermode="x unified")
                        
                        # ✅ TAMBAHKAN WATERMARK (OPSI 1)
                        fig.add_annotation(
                            text="© ssolihin99@gmail.com",
                            xref="paper", yref="paper",
                            x=0.99, y=0.01,  # Posisi: kanan bawah
                            showarrow=False,
                            font=dict(size=14, color="rgba(255,255,255,2)"),  # Semi-transparent
                            xanchor="right", yanchor="bottom"
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                
                # --- ISI DARI TAB 2 (TABEL) ---
                with tab2:
                    st.dataframe(merged_df.head(500), use_container_width=True) 
                    csv = merged_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download CSV Bersih",
                        data=csv,
                        file_name='Clean_Pump_Data.csv',
                        mime='text/csv',
                    )

        except Exception as e:
            st.error(f"Terjadi kesalahan: {e}")
        finally:
            os.remove(tmp_path)
else:
    with tab1:
        st.info("👋 Belum ada data yang diproses. Silakan unggah file H5 di panel sebelah kiri.")
    with tab2:
        st.info("👋 Tabel akan muncul di sini setelah Anda mengunggah data.")
