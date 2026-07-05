import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.dates as mdates
import ast
import io
import base64

import matplotlib
matplotlib.use('Agg') # Use non-interactive backend

def build_cinematic_replay(csv_file="presentation_data.csv", output_file="backtest_replay.gif", speed_multiplier=5):
    # This function remains for compatibility but the core logic will be in stream_cinematic_replay
    print("Note: build_cinematic_replay is being called, but streaming is the preferred method.")
    # You could choose to either save a GIF here as before, or just log a message.
    # For now, let's keep the GIF generation logic.
    
    print("Loading backtest data...")
    df = pd.read_csv(csv_file)
    df['Date'] = pd.to_datetime(df['Date'])
    
    regime_map = {0.0: 'Bear', 1.0: 'Kangaroo', 2.0: 'Bull'}
    regime_colors = {'Bear': '#ff6b6b', 'Kangaroo': '#feca57', 'Bull': '#1dd1a1'}
    df['Regime_Name'] = df['Regime'].map(regime_map)

    plt.style.use('dark_background')
    plt.rcParams['text.color'] = '#cfcfcf'
    plt.rcParams['axes.labelcolor'] = '#cfcfcf'
    plt.rcParams['xtick.color'] = '#cfcfcf'
    plt.rcParams['ytick.color'] = '#cfcfcf'
    
    fig, ax = plt.subplots(figsize=(14, 8))
    # ... (rest of the GIF generation code can remain here if you want a fallback)
    pass


def stream_cinematic_replay(csv_file, socketio, client_id, speed_multiplier=5, return_final_frame=False):
    """
    Generates the cinematic replay frame by frame and streams it over a WebSocket.
    """
    print("Loading backtest data for streaming...")
    df = pd.read_csv(csv_file)
    df['Date'] = pd.to_datetime(df['Date'])
    
    regime_map = {0.0: 'Bear', 1.0: 'Kangaroo', 2.0: 'Bull'}
    regime_colors = {'Bear': '#ff6b6b', 'Kangaroo': '#feca57', 'Bull': '#1dd1a1'}
    df['Regime_Name'] = df['Regime'].map(regime_map)

    plt.style.use('dark_background')
    plt.rcParams['text.color'] = '#cfcfcf'
    plt.rcParams['axes.labelcolor'] = '#cfcfcf'
    plt.rcParams['xtick.color'] = '#cfcfcf'
    plt.rcParams['ytick.color'] = '#cfcfcf'
    
    fig, ax = plt.subplots(figsize=(14, 8))
    fig.patch.set_facecolor('#121212')
    ax.set_facecolor('#121212')
    
    ax.set_xlim(df['Date'].min(), df['Date'].max())
    ax.set_ylim(df['Portfolio_Value'].min() * 0.95, df['Portfolio_Value'].max() * 1.1)
    
    ax.grid(False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color('#444')
    ax.spines['left'].set_color('#444')

    df['Regime_Shift'] = df['Regime'].diff().fillna(0)
    shift_indices = df.index[df['Regime_Shift'] != 0].tolist()
    shift_indices = [0] + shift_indices + [len(df) - 1]

    for i in range(len(shift_indices) - 1):
        start_idx = shift_indices[i]
        end_idx = shift_indices[i+1]
        regime_val = df['Regime_Name'].iloc[start_idx]
        color = regime_colors.get(regime_val, '#ffffff')
        ax.axvspan(
            df['Date'].iloc[start_idx], 
            df['Date'].iloc[end_idx], 
            color=color, alpha=0.6, lw=0, zorder=1
        )

    x_min, x_max = mdates.date2num(df['Date'].min()), mdates.date2num(df['Date'].max())
    y_min, y_max = ax.get_ylim()
    
    curtain = plt.Rectangle(
        (x_min, y_min), x_max - x_min, y_max - y_min, 
        color='#121212', zorder=2
    )
    ax.add_patch(curtain)

    line, = ax.plot([], [], color='#00d2ff', lw=2.5, zorder=3)
    
    hud_text = ax.text(
        0.02, 0.95, '', transform=ax.transAxes, 
        fontsize=14, color='#cfcfcf', verticalalignment='top',
        bbox=dict(boxstyle='round', facecolor='#1e1e1e', alpha=0.8, edgecolor='#333'),
        zorder=4
    )

    total_frames = len(df)
    frames_to_render = range(0, total_frames, speed_multiplier)
    
    print(f"Beginning to stream {len(frames_to_render)} frames to client {client_id}...")

    for frame_num, frame in enumerate(frames_to_render):
        current_data = df.iloc[:frame+1]
        current_date = current_data['Date'].iloc[-1]
        current_val = current_data['Portfolio_Value'].iloc[-1]
        current_regime = current_data['Regime_Name'].iloc[-1]
        current_color = regime_colors[current_regime]
        
        line.set_data(current_data['Date'], current_data['Portfolio_Value'])
        
        current_x = mdates.date2num(current_date)
        curtain.set_x(current_x)
        curtain.set_width(x_max - current_x)
        
        raw_holdings = df['Holdings'].iloc[frame]
        try:
            holdings = ast.literal_eval(raw_holdings)
            holdings_str = "100% Cash (BIL)" if not holdings else " | ".join([f"{k}: {v:.1%}" for k, v in holdings.items()])
        except:
            holdings_str = "No Data"

        hud_text.set_text(
            f"Date: {current_date.strftime('%Y-%m-%d')}\n"
            f"Portfolio Value: ${current_val:,.2f}\n"
            f"Market Weather: {current_regime}\n"
            f"Holdings: {holdings_str}"
        )
        hud_text.get_bbox_patch().set_edgecolor(current_color)
        hud_text.get_bbox_patch().set_linewidth(2)

        # Render the current frame to an in-memory buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.1, facecolor=fig.get_facecolor())
        buf.seek(0)
        
        # Encode the image in base64 and send it over the WebSocket
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        
        progress = (frame_num + 1) / len(frames_to_render) * 100
        
        socketio.emit('backtest_frame', {
            'frame': img_str,
            'progress': progress
        }, room=client_id)
        
        # A small sleep to prevent overwhelming the network and to control the frame rate
        socketio.sleep(0.03) 

    plt.close(fig) # Important: close the figure to free up memory
    print(f"Finished streaming frames to client {client_id}.")
    
    # Signal that the stream is complete
    socketio.emit('stream_complete', {'message': 'Backtest video stream finished.'}, room=client_id)

    if return_final_frame:
        # Re-render the very last frame to return it
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0.1, facecolor=fig.get_facecolor())
        buf.seek(0)
        final_img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return final_img_str
    
    plt.close(fig) # Important: close the figure to free up memory
