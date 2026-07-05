import pandas as pd
import plotly.graph_objects as go
import ast

def build_presentation_dashboard(csv_file="presentation_data.csv"):
    print("Loading backtest data...")
    df = pd.read_csv(csv_file)
    df['Date'] = pd.to_datetime(df['Date'])
    
    # Map the numeric regimes to readable names and colors
    regime_map = {0.0: 'Bear', 1.0: 'Kangaroo', 2.0: 'Bull'}
    regime_colors = {
        'Bear': "#ff6d6d",     # Vibrant soft red
        'Kangaroo': '#feca57', # Warm amber/gold
        'Bull': '#1dd1a1'      # Bright mint/neon green
    }
    df['Regime_Name'] = df['Regime'].map(regime_map)

    # Format the holdings dictionary into a clean HTML list for the hover tooltip
    def format_holdings(row):
        try:
            holdings = ast.literal_eval(row['Holdings'])
            if not holdings:
                return "100% Cash"
            return "<br>".join([f"{ticker}: {weight:.1%}" for ticker, weight in holdings.items()])
        except:
            return "No Data"

    df['Hover_Holdings'] = df.apply(format_holdings, axis=1)

    print("Building interactive dashboard...")
    fig = go.Figure()

    # 1. Add the main Equity Curve
    fig.add_trace(go.Scatter(
        x=df['Date'],
        y=df['Portfolio_Value'],
        mode='lines',
        name='Portfolio Value',
        line=dict(color="#03d1ff", width=2), # Upgraded to Electric Cyan
        # This formatting string is the magic that makes the hover box look professional
        hovertemplate=(
            "<b>Date:</b> %{x}<br>"
            "<b>Value:</b> $%{y:,.2f}<br>"
            "<b>Regime:</b> %{customdata[0]}<br>"
            "<br><b>Holdings:</b><br>%{customdata[1]}"
            "<extra></extra>" # Hides the redundant trace name
        ),
        customdata=df[['Regime_Name', 'Hover_Holdings']]
    ))

    # 2. Add background colors to show the HMM Regime periods
    # We find where the regime changes to draw rectangles
    df['Regime_Shift'] = df['Regime'].diff().fillna(0)
    shift_indices = df.index[df['Regime_Shift'] != 0].tolist()
    shift_indices = [0] + shift_indices + [len(df) - 1]

    for i in range(len(shift_indices) - 1):
        start_idx = shift_indices[i]
        end_idx = shift_indices[i+1]
        
        regime_val = df['Regime_Name'].iloc[start_idx]
        color = regime_colors.get(regime_val, '#ffffff')
        
        fig.add_vrect(
            x0=df['Date'].iloc[start_idx], 
            x1=df['Date'].iloc[end_idx],
            fillcolor=color, 
            opacity=0.7, 
            layer="below", 
            line_width=0
        )

    # 3. Format the Layout
    # fig.update_layout(
    #     title=dict(text='HMM Multi-Asset Strategy: 10-Year Backtest', font=dict(size=24)),
    #     xaxis_title='Date',
    #     yaxis_title='Portfolio Value ($)',
    #     template='plotly_dark',
    #     hovermode="x unified", # Creates a clean vertical crosshair
    #     xaxis=dict(
    #         rangeslider=dict(visible=True), # Adds the timeline scrubber at the bottom
    #         type="date"
    #     )
    # )

    # 3. Format the Layout
    fig.update_layout(
        title=dict(text='HMM Multi-Asset Strategy: 10-Year Backtest', font=dict(size=24, color='#e0e0e0')),
        xaxis_title='Date',
        yaxis_title='Portfolio Value ($)',
        template='plotly_dark',
        
        # FIX 1: The Global Font Color (Soft Off-White)
        font=dict(color='#cfcfcf'), 
        
        # Deepen the background slightly to make the neon lines pop more
        paper_bgcolor='#121212', 
        plot_bgcolor='#121212',
        
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#1e1e1e",       # Dark gray tooltip background
            font_color="#cfcfcf",    # Soft white tooltip text
            bordercolor="#333333"    # Subtle border
        ),
        
        xaxis=dict(
            # FIX 2: Invert the Rangeslider "Shadow"
            rangeslider=dict(
                visible=True,
                bgcolor="#2a2a2a",     # Lightens the scrubber background
                bordercolor="#444444", # Subtle highlight border
                borderwidth=1
            ),
            type="date",
            gridcolor='#2b2b2b'        # Soften the vertical gridlines
        ),
        yaxis=dict(
            gridcolor='#2b2b2b'        # Soften the horizontal gridlines
        )
    )

    # Export to a standalone HTML file
    output_file = "Interactive_Presentation.html"
    fig.write_html(output_file)
    print(f"Success! Open '{output_file}' in your web browser.")

if __name__ == "__main__":
    build_presentation_dashboard()