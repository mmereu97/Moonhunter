import sys
import requests
import time as unix_time
from datetime import datetime, timedelta
import pytz
import os
import pandas as pd
import json
from timezonefinder import TimezoneFinder
from PyQt5.QtWidgets import (QCheckBox, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox, 
                             QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel, 
                             QLineEdit, QMainWindow, QMessageBox, QProgressDialog, QPushButton, 
                             QApplication, QScrollArea, QSpinBox, QTimeEdit, QVBoxLayout, QWidget)
from PyQt5.QtCore import Qt, QTimer, QPointF, QDateTime, QTime
from PyQt5.QtGui import QPixmap, QFont, QPalette, QPainter, QBrush, QColor
import math
from skyfield.api import load, Topos
from skyfield import almanac

class MeteoDataManager:
    def __init__(self, excel_path: str = "lista_localitati_cu_statii.xlsx"):
        self.excel_path = excel_path
        self.csv_path = excel_path.replace('.xlsx', '.csv')
        self.data = self._load_data()
        
    def _load_data(self):
        try:
            if os.path.exists(self.csv_path):
                df = pd.read_csv(self.csv_path, encoding='utf-8-sig')
                print(f"Încărcat {df.shape[0]} localități din CSV")
            else:
                df = pd.read_excel(self.excel_path)
                print("Date încărcate din Excel")

            required_columns = ['Județ', 'Localitate', 'administrare', 'Latitudine N', 'Longitudine E']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Lipsesc coloanele: {', '.join(missing_columns)}")

            df['Județ'] = df['Județ'].fillna('').str.strip()
            df['Localitate'] = df['Localitate'].fillna('').str.strip()
            df['administrare'] = df['administrare'].fillna('').str.strip()
            
            data_dict = {}
            
            for _, row in df.iterrows():
                judet = row['Județ']
                localitate = row['Localitate']
                administrare = row['administrare'] if pd.notna(row['administrare']) else ''
                
                if not judet or not localitate:
                    continue
                    
                if judet not in data_dict:
                    data_dict[judet] = {}
                    
                data_dict[judet][localitate] = {
                    "latitude": float(row['Latitudine N']) if pd.notna(row['Latitudine N']) else 0,
                    "longitude": float(row['Longitudine E']) if pd.notna(row['Longitudine E']) else 0,
                    "administrare": administrare.lower()
                }
            
            print(f"\nDate încărcate cu succes:")
        
            return data_dict
                
        except Exception as e:
            print(f"Eroare la încărcarea datelor: {str(e)}")
            return {}
    
    def get_judete(self) -> list:
        return sorted(self.data.keys())
    
    def get_localitati(self, judet: str, hide_comune: bool = False) -> list:
        localitati = self.data.get(judet, {})
        if hide_comune:
            return sorted([loc for loc, data in localitati.items() 
                         if not data['administrare'].startswith('comuna')])
        return sorted(localitati.keys())
    
    def get_coordinates(self, judet: str, localitate: str):
        location_data = self.data.get(judet, {}).get(localitate, {})
        return location_data.get('latitude', 0), location_data.get('longitude', 0)

class CompassWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(384, 384)
        self.setMaximumSize(384, 384)
        self.current_azimuth = 0
        self.rise_azimuth = 0
        self.moon_visible = False
        self.distance_color = "#FFC107"  # default galben
        
    def update_position(self, current_azimuth, rise_azimuth, is_visible, distance_color="#FFC107"):
        self.current_azimuth = current_azimuth
        self.rise_azimuth = rise_azimuth
        self.moon_visible = is_visible
        self.distance_color = distance_color
        self.update()
        
    def paintEvent(self, event):
        super().paintEvent(event)
        pixmap = QPixmap("compass.png")
        if not pixmap.isNull():
            self.setPixmap(pixmap)
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        center = self.rect().center()
        radius = min(self.width(), self.height()) / 2 - 20
        
        def azimuth_to_xy(azimuth):
            angle = math.radians(90 - azimuth)
            x = center.x() + radius * math.cos(angle)
            y = center.y() - radius * math.sin(angle)
            return QPointF(x, y)
        
        current_pos = azimuth_to_xy(self.current_azimuth)
        
        if self.moon_visible:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(self.distance_color)))
            painter.drawEllipse(current_pos, 8, 8)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#0d47a1")))
            painter.drawEllipse(current_pos, 8, 8)
            
            rise_pos = azimuth_to_xy(self.rise_azimuth)
            painter.setBrush(QBrush(QColor(self.distance_color)))
            painter.drawEllipse(rise_pos, 8, 8)
        
        painter.end()

class MoonProgressDialog(QProgressDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModal)
        self.setMinimumDuration(0)  # Apare imediat
        self.setAutoClose(True)
        self.setAutoReset(True)
        self.setMinimum(0)
        self.setMaximum(100)
        # Setăm dimensiunea minimă pentru a asigura că tot textul este vizibil
        self.setMinimumWidth(400)
        self.setMinimumHeight(150)
        # Stilizare pentru tema dark și aspect profesional
        self.setStyleSheet("""
            QProgressDialog {
                background-color: #2b2b2b;
                color: white;
                min-width: 400px;
                min-height: 150px;
            }
            QProgressDialog QLabel {
                color: white;
                font-size: 12px;
                min-height: 50px;
                padding: 10px;
            }
            QProgressBar {
                border: 2px solid #404040;
                border-radius: 5px;
                text-align: center;
                background-color: #2b2b2b;
                min-height: 25px;
                max-height: 25px;
                margin: 10px;
            }
            QProgressBar::chunk {
                background-color: #0d47a1;
                margin: 0.5px;
            }
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
        """)
        # Setăm un text pentru butonul Cancel
        self.setCancelButtonText("Anulează")
    
class FullMoonDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Rating luni pline")
        self.setMinimumWidth(500)
        self.setMinimumHeight(650)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
            }
            QLabel {
                color: white;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(3)
        
        title = QLabel("Rating luni pline - următoarele 12 luni")
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 3px;")
        layout.addWidget(title)
        
        self.ratings_widget = QWidget()
        self.ratings_layout = QVBoxLayout()
        self.ratings_widget.setLayout(self.ratings_layout)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.ratings_widget)
        layout.addWidget(scroll)
        
        self.setLayout(layout)
        
        ratings = self.parent.calculate_full_moon_ratings(force_recalc=True)
        self.update_ratings_display(ratings)
        
    def load_ratings(self):
        """Încarcă și afișează rating-urile salvate"""
        ratings = self.parent.load_full_moon_ratings()
        self.update_ratings_display(ratings)
        
    def recalculate(self):
        """Recalculează rating-urile"""
        self.recalc_btn.setEnabled(False)
        self.recalc_btn.setText("Se calculează...")
        
        # Folosim QTimer pentru a nu bloca interfața
        QTimer.singleShot(100, self._do_recalculate)
        
    def _do_recalculate(self):
        try:
            ratings = self.parent.calculate_full_moon_ratings(force_recalc=True)
            self.update_ratings_display(ratings)
        finally:
            self.recalc_btn.setEnabled(True)
            self.recalc_btn.setText("Recalculează")
    
    def update_ratings_display(self, ratings):
        """Actualizează afișarea rating-urilor cu format detaliat"""
        while self.ratings_layout.count():
            item = self.ratings_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
                
        for rating in ratings:
            container = QWidget()
            container.setStyleSheet("background-color: #333333; border-radius: 4px; margin: 2px;")
            line_layout = QHBoxLayout()
            
            # Data în stânga
            date_str = rating['date'].strftime('%d.%m.%Y')
            date_label = QLabel(date_str)
            date_label.setStyleSheet("color: white; font-family: monospace; min-width: 100px;")
            
            # Calculăm distanța pentru această dată
            ts = self.parent.ts.from_datetime(rating['date'])
            distance_info = self.parent.calculate_moon_distance_at(ts)
            
            if distance_info:
                # Determinăm statusul bazat pe rating
                if rating['rating'] >= 8:
                    status = "PERIGEU"
                elif rating['rating'] <= 3:
                    status = "APOGEU"
                else:
                    status = "INTERMEDIAR"
                    
                # Formatăm distanța cu puncte pentru mii
                distance_str = f"{distance_info['distance']:,.0f}".replace(",", ".")
                
                # Creăm textul complet
                status_text = f"{status} ({rating['rating']}/10) • {distance_str} km"
                rating_label = QLabel(status_text)
                
                # Setăm culoarea bazată pe rating
                if rating['rating'] >= 8:
                    color = "#4CAF50"  # verde
                elif rating['rating'] >= 5:
                    color = "#FFC107"  # galben
                else:
                    color = "#F44336"  # roșu
                    
                rating_label.setStyleSheet(f"color: {color}; font-family: monospace; font-weight: bold;")
            else:
                rating_label = QLabel(f"Rating: {rating['rating']}/10")
                rating_label.setStyleSheet("color: white; font-family: monospace;")
            
            line_layout.addWidget(date_label)
            line_layout.addWidget(rating_label)
            line_layout.addStretch()
            container.setLayout(line_layout)
            
            self.ratings_layout.addWidget(container)
            
        self.ratings_layout.addStretch()
        
    def get_rating_color(self, rating):
        """Returnează culoarea pentru un rating"""
        if rating >= 8:
            return "#4CAF50"  # verde pentru aproape de perigeu
        elif rating >= 5:
            return "#FFC107"  # galben pentru distanță intermediară
        else:
            return "#F44336"  # roșu pentru aproape de apogeu
            
class LocationProfile:
    def __init__(self, name, latitude, longitude, timezone=None):
        self.name = name
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone

    def to_dict(self):
        return {
            'name': self.name,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'timezone': self.timezone
        }

    @staticmethod
    def from_dict(data):
        return LocationProfile(
            data['name'],
            data['latitude'],
            data['longitude'],
            data.get('timezone')
        )

class ProfileManager:
    def __init__(self, settings_file='moon_settings.json'):
        self.settings_file = settings_file
        self.profiles = {}
        self.load_profiles()

    def load_profiles(self):
        try:
            with open(self.settings_file, 'r') as f:
                data = json.load(f)
                self.profiles = {
                    name: LocationProfile.from_dict(profile_data)
                    for name, profile_data in data.get('profiles', {}).items()
                }
        except FileNotFoundError:
            self.profiles = {}

    def save_profiles(self):
        try:
            with open(self.settings_file, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}

        data['profiles'] = {
            name: profile.to_dict()
            for name, profile in self.profiles.items()
        }

        with open(self.settings_file, 'w') as f:
            json.dump(data, f, indent=4)

    def add_profile(self, profile):
        self.profiles[profile.name] = profile
        self.save_profiles()

    def remove_profile(self, name):
        if name in self.profiles:
            del self.profiles[name]
            self.save_profiles()

    def get_profile(self, name):
        return self.profiles.get(name)

    def get_all_profiles(self):
        return list(self.profiles.keys())

class TimeshiftWidget(QGroupBox):
    def __init__(self, parent=None):
        super().__init__("Time Shift", parent)
        self.parent = parent
        self.init_ui()
        self.is_timeshifted = False
        self.original_palette = None
        
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(3)
        
        # Left navigation button
        self.left_button = QPushButton("←")
        self.left_button.setFixedWidth(40)
        self.left_button.clicked.connect(self.navigate_left)
        
        # DateTime picker cu font mai mare și culoare albă
        self.datetime_picker = QDateTimeEdit(self)
        self.datetime_picker.setDateTime(QDateTime.currentDateTime())
        self.datetime_picker.setCalendarPopup(True)
        self.datetime_picker.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.datetime_picker.setStyleSheet("""
            QDateTimeEdit {
                color: white;
                font-size: 14px;
                padding: 5px;
            }
        """)
        
        # Right navigation button
        self.right_button = QPushButton("→")
        self.right_button.setFixedWidth(40)
        self.right_button.clicked.connect(self.navigate_right)
        
        # Timeshift button
        self.timeshift_button = QPushButton("Time Shift", self)
        self.timeshift_button.clicked.connect(self.on_timeshift)
        
        # Unified reset button
        self.reset_button = QPushButton("Reset Time and Calendar", self)
        self.reset_button.clicked.connect(self.on_reset_all)
        
        # Error label
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: red;")
        self.error_label.hide()
        
        # Adăugăm totul pe un singur rând
        layout.addWidget(self.left_button)
        layout.addWidget(self.datetime_picker)
        layout.addWidget(self.right_button)
        layout.addWidget(self.timeshift_button)
        layout.addWidget(self.reset_button)
        layout.addWidget(self.error_label)
        layout.addStretch()
        
        self.setLayout(layout)

    def get_cursor_section(self):
        """Determină secțiunea în care se află cursorul în datetime picker"""
        cursor_pos = self.datetime_picker.lineEdit().cursorPosition()
        
        # Mapare poziții cursor la secțiuni (bazat pe formatul "dd/MM/yyyy HH:mm")
        if cursor_pos <= 2:  # dd
            return 'day'
        elif cursor_pos <= 5:  # MM
            return 'month'
        elif cursor_pos <= 10:  # yyyy
            return 'year'
        elif cursor_pos <= 13:  # HH
            return 'hour'
        else:  # mm
            return 'minute'

    def navigate_left(self):
        """Navigare la stânga bazată pe poziția cursorului"""
        current_datetime = self.datetime_picker.dateTime()
        section = self.get_cursor_section()
        
        if section == 'day':
            new_datetime = current_datetime.addDays(-1)
        elif section == 'month':
            new_datetime = current_datetime.addMonths(-1)
        elif section == 'year':
            new_datetime = current_datetime.addYears(-1)
        elif section == 'hour':
            new_datetime = current_datetime.addSecs(-3600)
        else:  # minute sau altă secțiune
            return
            
        self.datetime_picker.setDateTime(new_datetime)
        
    def navigate_right(self):
        """Navigare la dreapta bazată pe poziția cursorului"""
        current_datetime = self.datetime_picker.dateTime()
        section = self.get_cursor_section()
        
        if section == 'day':
            new_datetime = current_datetime.addDays(1)
        elif section == 'month':
            new_datetime = current_datetime.addMonths(1)
        elif section == 'year':
            new_datetime = current_datetime.addYears(1)
        elif section == 'hour':
            new_datetime = current_datetime.addSecs(3600)
        else:  # minute sau altă secțiune
            return
            
        self.datetime_picker.setDateTime(new_datetime)

    def on_reset_all(self):
        """Resetează atât calendarul cât și timeshift-ul"""
        # Resetăm datetime picker-ul
        current_time = QDateTime.currentDateTime()
        self.datetime_picker.setDateTime(current_time)
        
        # Resetăm timeshift-ul
        if hasattr(self.parent, 'timeshift_datetime'):
            delattr(self.parent, 'timeshift_datetime')
        if hasattr(self.parent, 'timeshift_ts'):
            delattr(self.parent, 'timeshift_ts')
            
        # Resetăm stylesheet-ul la original
        self.parent.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2b2b2b;
            }
            QGroupBox {
                border: 2px solid #404040;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QLabel, QCheckBox {
                color: white;
                font-size: 13px;
            }
            QComboBox, QLineEdit {
                background-color: #404040;
                color: white;
                border: 1px solid #505050;
                border-radius: 4px;
                padding: 5px;
                min-height: 25px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
        """)
        
        self.parent.update_moon_data()
        self.parent.print_moon_status()
        
    def on_timeshift(self):
        try:
            selected_datetime = self.datetime_picker.dateTime().toPyDateTime()
            current_datetime = QDateTime.currentDateTime().toPyDateTime()
            
            print("\n=== DEBUG TIMESHIFT COLORS ===")
            print(f"Current time: {current_datetime}")
            print(f"Selected time: {selected_datetime}")
            print(f"Going to: {'FUTURE' if selected_datetime > current_datetime else 'PAST'}")
            
            # Aplicăm timeshift
            self.parent.apply_timeshift(selected_datetime)
            
            # Definim stylesheet-ul pentru timeshift
            if selected_datetime > current_datetime:
                # Mov pentru viitor
                self.parent.setStyleSheet("""
                    QMainWindow, QWidget {
                        background-color: #2b2b3b;
                    }
                    QGroupBox {
                        border: 2px solid #404050;
                        border-radius: 6px;
                        margin-top: 12px;
                        padding-top: 10px;
                        color: white;
                        font-size: 13px;
                        font-weight: bold;
                    }
                    QLabel, QCheckBox {
                        color: white;
                        font-size: 13px;
                    }
                    QComboBox, QLineEdit {
                        background-color: #404050;
                        color: white;
                        border: 1px solid #505060;
                        border-radius: 4px;
                        padding: 5px;
                        min-height: 25px;
                        font-size: 13px;
                    }
                    QPushButton {
                        background-color: #0d47a1;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 8px 15px;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background-color: #1565c0;
                    }
                """)
            else:
                # Sepia pentru trecut
                self.parent.setStyleSheet("""
                    QMainWindow, QWidget {
                        background-color: #2b2b20;
                    }
                    QGroupBox {
                        border: 2px solid #404030;
                        border-radius: 6px;
                        margin-top: 12px;
                        padding-top: 10px;
                        color: white;
                        font-size: 13px;
                        font-weight: bold;
                    }
                    QLabel, QCheckBox {
                        color: white;
                        font-size: 13px;
                    }
                    QComboBox, QLineEdit {
                        background-color: #404030;
                        color: white;
                        border: 1px solid #505040;
                        border-radius: 4px;
                        padding: 5px;
                        min-height: 25px;
                        font-size: 13px;
                    }
                    QPushButton {
                        background-color: #0d47a1;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        padding: 8px 15px;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background-color: #1565c0;
                    }
                """)
                
            self.is_timeshifted = True
            self.error_label.hide()
            
        except Exception as e:
            print(f"TIMESHIFT ERROR: {str(e)}")
            self.error_label.setText(f"Eroare: {str(e)}")
            self.error_label.show()

class Scene:
    """Reprezintă o scenă fotografică cu toate condițiile necesare"""
    def __init__(self, name, location_type, location_data):
        self.name = name
        self.location_type = location_type
        self.location_data = location_data
        
        self.azimuth_min = 0
        self.azimuth_max = 360  
        self.elevation_min = 0
        self.elevation_max = 90
        
        self.time_start = "20:00"
        self.time_end = "23:00"
        self.time_end_next_day = False
        self.min_illumination = 0
        self.opportunities = []
        self.current_opportunity_index = 0
    
    def to_dict(self):
        print("\n=== DEBUG Scene.to_dict() ===")
        print(f"Salvare scenă: {self.name}")
        print(f"Număr oportunități de salvat: {len(self.opportunities)}")
        
        # Convert datetime objects to strings for JSON
        opportunities = []
        for i, opp in enumerate(self.opportunities):
            print(f"\nOportunitatea {i+1}:")
            opp_dict = opp.copy()
            print(f"  Original start: {opp_dict.get('start_datetime')}")
            print(f"  Original end: {opp_dict.get('end_datetime')}")
            
            if 'start_datetime' in opp_dict:
                if opp_dict['start_datetime'].tzinfo is None:
                    print("  Start datetime nu are timezone, adăugăm UTC")
                    opp_dict['start_datetime'] = pytz.UTC.localize(opp_dict['start_datetime'])
                formatted_start = opp_dict['start_datetime'].astimezone(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S %z')
                print(f"  Formatted start: {formatted_start}")
                opp_dict['start_datetime'] = formatted_start
                
            if 'end_datetime' in opp_dict:
                if opp_dict['end_datetime'].tzinfo is None:
                    print("  End datetime nu are timezone, adăugăm UTC")
                    opp_dict['end_datetime'] = pytz.UTC.localize(opp_dict['end_datetime'])
                formatted_end = opp_dict['end_datetime'].astimezone(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S %z')
                print(f"  Formatted end: {formatted_end}")
                opp_dict['end_datetime'] = formatted_end
                
            opportunities.append(opp_dict)
        
        data = {
            'name': self.name,
            'location_type': self.location_type,
            'location_data': self.location_data,
            'azimuth_min': self.azimuth_min,
            'azimuth_max': self.azimuth_max,
            'elevation_min': self.elevation_min,
            'elevation_max': self.elevation_max,
            'time_start': self.time_start,
            'time_end': self.time_end,
            'time_end_next_day': self.time_end_next_day,
            'min_illumination': self.min_illumination,
            'opportunities': opportunities,
            'current_opportunity_index': self.current_opportunity_index
        }
        print("\nDate finale pentru salvare:")
        print(f"Număr oportunități: {len(opportunities)}")
        print("=" * 50)
        return data

    @classmethod
    def from_dict(cls, data):
        """Creează o scenă din dicționar"""
        print("\n=== DEBUG Scene.from_dict() ===")
        print(f"Încărcare scenă: {data['name']}")
        print(f"Număr oportunități de încărcat: {len(data.get('opportunities', []))}")
        
        scene = cls(data['name'], data['location_type'], data['location_data'])
        for key, value in data.items():
            if key == 'opportunities':
                print("\nProcesare oportunități:")
                opportunities = []
                for i, opp in enumerate(value):
                    print(f"\nOportunitatea {i+1}:")
                    opp_dict = opp.copy()
                    
                    if 'start_datetime' in opp_dict:
                        print(f"  Loading start: {opp_dict['start_datetime']}")
                        try:
                            # Parsăm data și timezone-ul
                            dt_str = opp_dict['start_datetime'].split('+')[0].strip()
                            dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                            dt_utc = pytz.UTC.localize(dt)
                            opp_dict['start_datetime'] = dt_utc
                            print(f"  Parsed start: {dt_utc}")
                        except Exception as e:
                            print(f"  !!! EROARE la parsare start_datetime: {e}")
                            
                    if 'end_datetime' in opp_dict:
                        print(f"  Loading end: {opp_dict['end_datetime']}")
                        try:
                            dt_str = opp_dict['end_datetime'].split('+')[0].strip()
                            dt = datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
                            dt_utc = pytz.UTC.localize(dt)
                            opp_dict['end_datetime'] = dt_utc
                            print(f"  Parsed end: {dt_utc}")
                        except Exception as e:
                            print(f"  !!! EROARE la parsare end_datetime: {e}")
                    
                    opportunities.append(opp_dict)
                
                print(f"\nTotal oportunități încărcate: {len(opportunities)}")
                scene.opportunities = opportunities
            else:
                setattr(scene, key, value)
        
        print("\nÎncărcare completă")
        print("=" * 50)
        return scene

class SceneEditorWindow(QMainWindow):
    """Fereastra pentru editarea scenelor fotografice"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Scene Editor")
        self.setMinimumSize(800, 600)
        self.scenes = []
        self.opportunity_labels = {}
        self.use_strict_checkbox = QCheckBox("Use strict boundaries for opportunity calculation")
        self.use_strict_checkbox.setChecked(False)
        
        # Setăm stylesheet-ul pentru această fereastră
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2b2b2b;
            }
            QGroupBox {
                border: 2px solid #404040;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 10px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QLabel {
                color: white;
            }
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
            }
        """)
        
        # Widget central și layout principal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Header cu buton New Scene
        header = QHBoxLayout()
        self.new_scene_btn = QPushButton("New Scene")
        self.new_scene_btn.clicked.connect(self.create_new_scene)
        header.addWidget(self.new_scene_btn)
        header.addStretch()
        layout.addLayout(header)
        
        # Zonă scrollabilă pentru scene
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.scenes_container = QWidget()
        self.scenes_layout = QVBoxLayout()
        self.scenes_container.setLayout(self.scenes_layout)
        scroll.setWidget(self.scenes_container)
        layout.addWidget(scroll)
        
        # Încarcă scenele salvate
        try:
            self.load_scenes()
        except Exception as e:
            print(f"Eroare la încărcarea scenelor în constructor: {e}")
            self.scenes = []

    def get_current_location_data(self):
        """Obține datele locației curente"""
        print("\n=== DEBUG GET_CURRENT_LOCATION_DATA ===")
        try:
            print(f"Active view: {self.parent.settings['active_view']}")
            if self.parent.settings['active_view'] == 'romania':
                data = {
                    'judet': self.parent.judet_combo.currentText(),
                    'localitate': self.parent.localitate_combo.currentText(),
                    'lat': self.parent.location.latitude.degrees,
                    'lon': self.parent.location.longitude.degrees
                }
                print(f"Date România: {data}")
                return data
            elif self.parent.settings['active_view'] == 'profile':
                profile = self.parent.profile_manager.get_profile(
                    self.parent.profile_combo.currentText())
                data = {
                    'name': profile.name,
                    'lat': profile.latitude,
                    'lon': profile.longitude,
                    'timezone': profile.timezone
                }
                print(f"Date profil: {data}")
                return data
            else:  # gps
                coords = self.parent.gps_input.text().strip().split()
                data = {
                    'lat': float(coords[0]),
                    'lon': float(coords[1])
                }
                print(f"Date GPS: {data}")
                return data
        except Exception as e:
            print(f"EROARE la obținerea datelor locației: {str(e)}")
            import traceback
            traceback.print_exc()
            raise

    def create_new_scene(self, scene_to_edit=None):
        """Creează sau editează o scenă"""
        print("\n=== DEBUG CREATE_NEW_SCENE ===")
        print(f"Scene to edit: {scene_to_edit}")
        
        try:
            dialog = QDialog(self)
            print("Dialog creat")
            dialog.setWindowTitle("New Scene" if not scene_to_edit else "Edit Scene")
            dialog.setStyleSheet("""
                QDialog {
                    background-color: #2b2b2b;
                }
                QLabel {
                    color: white;
                }
                QGroupBox {
                    color: white;
                }
                QSpinBox {
                    background-color: #404040;
                    color: white;
                    border: 1px solid #505050;
                    padding: 5px;
                }
                QLineEdit {
                    background-color: #404040;
                    color: white;
                    border: 1px solid #505050;
                    padding: 5px;
                }
                QTimeEdit {
                    background-color: #404040;
                    color: white;
                    border: 1px solid #505050;
                    padding: 5px;
                }
                QCheckBox {
                    color: white;
                }
            """)
            layout = QVBoxLayout()
            
            # Numele scenei
            name_layout = QHBoxLayout()
            name_layout.addWidget(QLabel("Scene Name:"))
            name_input = QLineEdit()
            name_input.setText(scene_to_edit.name if scene_to_edit else "")
            name_layout.addWidget(name_input)
            layout.addLayout(name_layout)
            
            # Limite largi
            wide_group = QGroupBox("Wide Boundaries")
            wide_layout = QFormLayout()
            
            wide_az_min = QSpinBox()
            wide_az_min.setRange(0, 360)
            wide_az_min.setValue(scene_to_edit.azimuth_min if scene_to_edit else 0)
            
            wide_az_max = QSpinBox()
            wide_az_max.setRange(0, 360)
            wide_az_max.setValue(scene_to_edit.azimuth_max if scene_to_edit else 360)
            
            wide_el_min = QSpinBox()
            wide_el_min.setRange(0, 90)
            wide_el_min.setValue(scene_to_edit.elevation_min if scene_to_edit else 0)
            
            wide_el_max = QSpinBox()
            wide_el_max.setRange(0, 90)
            wide_el_max.setValue(scene_to_edit.elevation_max if scene_to_edit else 90)
            
            wide_layout.addRow("Azimuth Min (°):", wide_az_min)
            wide_layout.addRow("Azimuth Max (°):", wide_az_max)
            wide_layout.addRow("Elevation Min (°):", wide_el_min)
            wide_layout.addRow("Elevation Max (°):", wide_el_max)
            wide_group.setLayout(wide_layout)
            layout.addWidget(wide_group)
            
            # Interval orar
            time_group = QGroupBox("Time Window")
            time_layout = QFormLayout()
            
            time_start = QTimeEdit()
            time_start.setDisplayFormat("HH:mm")
            if scene_to_edit:
                h, m = map(int, scene_to_edit.time_start.split(':'))
                time_start.setTime(QTime(h, m))
            else:
                time_start.setTime(QTime(20, 0))
            
            time_end = QTimeEdit()
            time_end.setDisplayFormat("HH:mm")
            if scene_to_edit:
                h, m = map(int, scene_to_edit.time_end.split(':'))
                time_end.setTime(QTime(h, m))
            else:
                time_end.setTime(QTime(23, 0))
            
            time_end_next_day = QCheckBox("Ends next day")
            if scene_to_edit:
                time_end_next_day.setChecked(scene_to_edit.time_end_next_day)
            
            time_layout.addRow("Start Time:", time_start)
            time_layout.addRow("End Time:", time_end)
            time_layout.addRow(time_end_next_day)
            time_group.setLayout(time_layout)
            layout.addWidget(time_group)
            
            # Iluminare minimă
            illum_group = QGroupBox("Moon Illumination")
            illum_layout = QHBoxLayout()
            illum_spin = QSpinBox()
            illum_spin.setRange(0, 100)
            illum_spin.setSuffix("%")
            illum_spin.setValue(scene_to_edit.min_illumination if scene_to_edit else 0)
            illum_layout.addWidget(QLabel("Minimum Illumination:"))
            illum_layout.addWidget(illum_spin)
            illum_layout.addStretch()
            illum_group.setLayout(illum_layout)
            layout.addWidget(illum_group)
            
            # Butoane
            button_layout = QHBoxLayout()
            ok_button = QPushButton("OK")
            ok_button.clicked.connect(dialog.accept)
            ok_button.setStyleSheet("""
                QPushButton {
                    background-color: #0d47a1;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 15px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #1565c0;
                }
            """)
            
            cancel_button = QPushButton("Cancel")
            cancel_button.clicked.connect(dialog.reject)
            cancel_button.setStyleSheet("""
                QPushButton {
                    background-color: #666666;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 15px;
                    min-width: 80px;
                }
                QPushButton:hover {
                    background-color: #888888;
                }
            """)
            
            button_layout.addStretch()
            button_layout.addWidget(ok_button)
            button_layout.addWidget(cancel_button)
            layout.addLayout(button_layout)
            
            dialog.setLayout(layout)
            
            if dialog.exec_() == QDialog.Accepted:
                print("Dialog accepted - începe procesarea")
                try:
                    if not scene_to_edit:
                        print("Creăm scenă nouă")
                        current_location = self.get_current_location_data()
                        print(f"Date locație: {current_location}")
                        scene = Scene(
                            name_input.text(),
                            self.parent.settings['active_view'],
                            current_location
                        )
                    else:
                        print("Actualizăm scenă existentă")
                        scene = scene_to_edit
                        scene.name = name_input.text()
                    
                    # Setăm limitele
                    print("Setăm limitele")
                    scene.azimuth_min = wide_az_min.value()
                    scene.azimuth_max = wide_az_max.value()
                    scene.elevation_min = wide_el_min.value()
                    scene.elevation_max = wide_el_max.value()
                    
                    # Setăm intervalul orar
                    print("Setăm intervalul orar")
                    scene.time_start = time_start.time().toString("HH:mm")
                    scene.time_end = time_end.time().toString("HH:mm")
                    scene.time_end_next_day = time_end_next_day.isChecked()
                    
                    # Setăm iluminarea
                    scene.min_illumination = illum_spin.value()
                    
                    if not scene_to_edit:
                        print("Adăugăm scena în listă")
                        self.scenes.append(scene)
                        
                    print("Calculăm oportunități")
                    self.compute_opportunities(scene)
                    
                    # Reîmprospătăm interfața indiferent dacă e scenă nouă sau editată
                    print("Actualizăm interfața")
                    # Golim layout-ul
                    for i in reversed(range(self.scenes_layout.count())):
                        widget = self.scenes_layout.itemAt(i).widget()
                        if widget:
                            widget.setParent(None)
                    
                    # Reconstruim widget-urile pentru toate scenele
                    for s in self.scenes:
                        new_widget = self.create_scene_widget(s)
                        self.scenes_layout.addWidget(new_widget)
                        
                    print("Salvăm scenele")
                    self.save_scenes()
                    print("Procesare completă")
                    
                except Exception as e:
                    print(f"EROARE la procesarea scenei: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    
        except Exception as e:
            print(f"EROARE la crearea dialogului: {str(e)}")
            import traceback
            traceback.print_exc()

    def duplicate_scene(self, scene):
        """Duplică o scenă existentă"""
        new_scene = Scene(
            f"{scene.name} (copie)",
            scene.location_type,
            scene.location_data.copy()
        )
        
        # Copiază toate atributele
        for attr in ['wide_azimuth_min', 'wide_azimuth_max', 'wide_elevation_min', 
                    'wide_elevation_max', 'strict_azimuth_min', 'strict_azimuth_max',
                    'strict_elevation_min', 'strict_elevation_max', 'time_start',
                    'time_end', 'time_end_next_day', 'min_illumination']:
            setattr(new_scene, attr, getattr(scene, attr))
            
        self.scenes.append(new_scene)
        self.compute_opportunities(new_scene)
        self.scenes_layout.addWidget(self.create_scene_widget(new_scene))
        self.save_scenes()

    def delete_scene(self, scene):
        """Șterge o scenă"""
        reply = QMessageBox.question(self, 'Ștergere Scenă',
                                   f'Sigur vrei să ștergi scena "{scene.name}"?',
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
                                   
        if reply == QMessageBox.Yes:
            self.scenes.remove(scene)
            # Reîmprospătăm interfața
            for i in reversed(range(self.scenes_layout.count())): 
                self.scenes_layout.itemAt(i).widget().setParent(None)
            for scene in self.scenes:
                self.scenes_layout.addWidget(self.create_scene_widget(scene))
            self.save_scenes()
            self.parent.update_next_opportunity()  # Când se șterge o scenă

    def create_scene_widget(self, scene):
        """Creează widget-ul pentru o scenă fără butoane de navigare"""
        widget = QGroupBox(scene.name)
        layout = QVBoxLayout()
        layout.setSpacing(2)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Rândul 1: Butoane
        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(5)
        
        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(lambda: self.create_new_scene(scene))
        
        duplicate_btn = QPushButton("Duplicate")
        duplicate_btn.clicked.connect(lambda: self.duplicate_scene(scene))
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.delete_scene(scene))
        
        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.setToolTip("Recalculează oportunitățile pentru această scenă")
        refresh_btn.setStyleSheet("""
            QPushButton {
                min-width: 80px;
                padding: 8px 15px;
            }
        """)
        refresh_btn.clicked.connect(lambda: self.refresh_scene(scene))
        
        buttons_row.addWidget(edit_btn)
        buttons_row.addWidget(duplicate_btn)
        buttons_row.addWidget(delete_btn)
        buttons_row.addWidget(refresh_btn)
        buttons_row.addStretch()
        layout.addLayout(buttons_row)
        
        # Rândul 2: Locație
        if scene.location_type == 'romania':
            location_text = f"Locație: {scene.location_data['localitate']}, {scene.location_data['judet']}"
        elif scene.location_type == 'profile':
            location_text = f"Locație: {scene.location_data['name']}"
        else:
            location_text = f"Locație: {scene.location_data['lat']:.4f}°N, {scene.location_data['lon']:.4f}°E"
        layout.addWidget(QLabel(location_text))
        
        # Rândul 3: Limite
        limits_text = (f"Limite: Az {scene.azimuth_min}°-{scene.azimuth_max}°, "
                      f"El {scene.elevation_min}°-{scene.elevation_max}° | "
                      f"Timp: {scene.time_start}-{scene.time_end} "
                      f"{'(next day)' if scene.time_end_next_day else ''} | "
                      f"Iluminare min: {scene.min_illumination}%")
        layout.addWidget(QLabel(limits_text))
        
        # Rândul 4: Oportunități
        opps_row = QHBoxLayout()
        opps_row.setSpacing(10)
        
        if scene.opportunities:
            for i in range(min(3, len(scene.opportunities))):
                opp = scene.opportunities[i]
                interval_duration = opp['end_datetime'] - opp['start_datetime']
                minutes = int(interval_duration.total_seconds() / 60)
                
                # Calculăm distanța pentru momentul oportunității
                ts = self.parent.ts.from_datetime(opp['start_datetime'])
                distance_info = self.parent.calculate_moon_distance_at(ts)
                
                # Formatăm distanța cu rating
                distance_str = f"{distance_info['distance']:,.0f}".replace(",", ".")
                status_parts = distance_info['status'].split()
                rating_part = status_parts[-1]
                status_name = status_parts[0]
                distance_line = f"{status_name} {rating_part} • {distance_str} km"
                
                opp_label = QLabel(
                    f"Oportunitatea {i+1}:\n"
                    f"Data: {opp['start_datetime'].strftime('%d/%m/%Y')}\n"
                    f"Interval: {opp['start_datetime'].strftime('%H:%M')} - "
                    f"{opp['end_datetime'].strftime('%H:%M')}\n"
                    f"Durată: {minutes} minute\n"
                    f"Elevație: {opp['elevation_min']:.1f}° - {opp['elevation_max']:.1f}°\n"
                    f"Azimut: {opp['azimuth_min']:.1f}° - {opp['azimuth_max']:.1f}°\n"
                    f"Iluminare: {opp['max_illumination']:.1f}%\n"
                    f"{distance_line}"
                )
                opp_label.setStyleSheet("""
                    QLabel {
                        background-color: #404040;
                        padding: 1px;
                        border-radius: 4px;
                        min-width: 200px;
                        min-height: 105px;
                    }
                """)
                opp_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
                opp_label.setWordWrap(True)
                opps_row.addWidget(opp_label, 1)
        else:
            no_data_label = QLabel("Apăsați ↻ Refresh pentru a calcula oportunitățile")
            no_data_label.setStyleSheet("""
                QLabel {
                    background-color: #404040;
                    padding: 10px;
                    border-radius: 4px;
                    min-width: 200px;
                    min-height: 105px;
                }
            """)
            no_data_label.setAlignment(Qt.AlignCenter)
            opps_row.addWidget(no_data_label, 1)
        
        layout.addLayout(opps_row)
        widget.setLayout(layout)
        widget.setFixedHeight(250)
        
        return widget

    def refresh_scene(self, scene):
        """Recalculează oportunitățile pentru o singură scenă"""
        try:
            # Salvăm index-ul scenei în layout pentru a păstra ordinea
            scene_index = -1
            for i in range(self.scenes_layout.count()):
                widget = self.scenes_layout.itemAt(i).widget()
                if widget and widget.title() == scene.name:
                    scene_index = i
                    widget.setParent(None)
                    break
            
            # Recalculăm oportunitățile doar pentru această scenă
            self.compute_opportunities(scene)
            
            # Recreăm widget-ul scenei și îl punem înapoi în aceeași poziție
            new_widget = self.create_scene_widget(scene)
            if scene_index >= 0:
                self.scenes_layout.insertWidget(scene_index, new_widget)
            else:
                self.scenes_layout.addWidget(new_widget)
                
            # Salvăm modificările
            self.save_scenes()
            
            # Actualizăm afișarea oportunității
            self.parent.update_next_opportunity()
            
        except Exception as e:
            print(f"Eroare la recalcularea oportunităților pentru scena {scene.name}: {e}")

    def navigate_opportunities(self, scene, direction):
        """Navighează între oportunități"""
        print(f"\n=== Navigare oportunități pentru scena '{scene.name}' ===")
        print(f"Index curent: {scene.current_opportunity_index}, Direcție: {direction}")
        print(f"Total oportunități: {len(scene.opportunities)}")
        
        if not scene.opportunities:
            print("Nu există oportunități disponibile")
            return
            
        new_index = scene.current_opportunity_index + direction
        if 0 <= new_index < len(scene.opportunities):
            scene.current_opportunity_index = new_index
            print(f"Nou index: {new_index}")
            
            # Actualizăm afișarea pentru această scenă
            # Găsim widget-ul scenei și îl actualizăm
            for i in reversed(range(self.scenes_layout.count())):
                widget = self.scenes_layout.itemAt(i).widget()
                if widget and widget.title() == scene.name:
                    widget.setParent(None)
                    self.scenes_layout.insertWidget(i, self.create_scene_widget(scene))
                    break
                    
            self.save_scenes()
        else:
            print(f"Index invalid: {new_index}")

    def update_opportunity_display(self, scene):
        """Actualizează afișarea oportunității curente"""
        if scene.name not in self.opportunity_labels:
            self.opportunity_labels[scene.name] = QLabel()
            
        label = self.opportunity_labels[scene.name]
        label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #404040;
                padding: 10px;
                border-radius: 4px;
                margin-top: 10px;
            }
        """)
        
        if not scene.opportunities:
            label.setText("Nu s-au găsit oportunități")
            return
            
        opp = scene.opportunities[scene.current_opportunity_index]
        text = (f"Oportunitatea {scene.current_opportunity_index + 1}/{len(scene.opportunities)}\n"
                f"Data: {opp['datetime'].strftime('%d/%m/%Y %H:%M')}\n"
                f"Elevație: {opp['elevation']:.1f}°\n"
                f"Azimut: {opp['azimuth']:.1f}°\n"
                f"Iluminare: {opp['illumination']:.1f}%")
                
        label.setText(text)

    def compute_opportunities(self, scene, num_opportunities=3):
        """
        Calculează următoarele oportunități pentru o scenă, identificând intervale complete
        în care sunt îndeplinite toate condițiile simultan.
        """
        # Creăm dialogul de progres
        progress = MoonProgressDialog("Calculare Oportunități", self)
        progress.setLabelText(f"Se calculează oportunitățile pentru scena '{scene.name}'...")
        progress.setValue(0)
        
        print(f"\n=== Calculare oportunități pentru scena '{scene.name}' ===")
        scene.opportunities = []
        scene.current_opportunity_index = 0
        
        potential_intervals = []
        current_time = datetime.now(self.parent.current_timezone)
        days_to_check = 90
        
        print(f"Căutăm oportunități între {current_time.strftime('%d/%m/%Y')} și "
                      f"{(current_time + timedelta(days=days_to_check)).strftime('%d/%m/%Y')}")
        print(f"Condiții: Az {scene.azimuth_min}°-{scene.azimuth_max}°, "
              f"El {scene.elevation_min}°-{scene.elevation_max}°")
        print(f"Iluminare minimă: {scene.min_illumination}%")
        
        # Grupăm intervalele pe zile
        daily_intervals = {}
        current_interval = None
        
        try:
            for day in range(days_to_check):
                # Actualizăm progresul
                progress_value = int((day / days_to_check) * 100)
                progress.setValue(progress_value)
                progress.setLabelText(f"Se analizează ziua {day + 1} din {days_to_check}...")
                
                # Verificăm dacă utilizatorul a anulat operația
                if progress.wasCanceled():
                    print("Operație anulată de utilizator")
                    return
                    
                test_date = current_time + timedelta(days=day)
                date_key = test_date.date()
                print(f"\nVerificare ziua {day}: {date_key}")
                
                # Pentru fiecare zi, verificăm fiecare interval de 15 minute
                for hour in range(24):
                    if progress.wasCanceled():
                        return
                        
                    for minute in [0, 15, 30, 45]:
                        test_time = test_date.replace(hour=hour, minute=minute)
                        
                        # Verificăm fereastra de timp
                        time_str = test_time.strftime("%H:%M")
                        if not self.is_time_in_window(time_str, scene.time_start, 
                                                    scene.time_end, scene.time_end_next_day):
                            continue
                        
                        # Debug time window
                        print(f"\nVerificare {test_time.strftime('%H:%M')}")
                        
                        # Calculăm poziția lunii
                        try:
                            ts = self.parent.ts.from_datetime(test_time)
                            earth = self.parent.eph['earth']
                            moon = self.parent.eph['moon']
                            
                            astrometric = (earth + self.parent.location).at(ts).observe(moon)
                            alt, az, _ = astrometric.apparent().altaz()
                            
                            elevation = alt.degrees
                            azimuth = az.degrees
                            
                            print(f"  Poziție: El={elevation:.1f}°, Az={azimuth:.1f}°")
                            
                        except Exception as e:
                            print(f"!!! Eroare la calculul poziției: {e}")
                            continue
                        
                        conditions_met = (
                            self.is_azimuth_in_range(azimuth, scene.azimuth_min, scene.azimuth_max) and
                            scene.elevation_min <= elevation <= scene.elevation_max
                        )

                        print(f"  Condiții poziție: {conditions_met}")
                        
                        if not conditions_met:
                            if current_interval:
                                print("  Închid interval - condiții poziție nu mai sunt îndeplinite")
                                current_interval['end_datetime'] = test_time - timedelta(minutes=15)
                                if date_key not in daily_intervals:
                                    daily_intervals[date_key] = []
                                daily_intervals[date_key].append(current_interval)
                                current_interval = None
                            continue
                        
                        # Verificăm iluminarea
                        try:
                            timestamp = int(test_time.timestamp())
                            response = requests.get(f'https://api.farmsense.net/v1/moonphases/?d={timestamp}')
                            moon_data = response.json()[0]
                            illumination = float(moon_data['Illumination']) * 100
                           
                            print(f"  Iluminare: {illumination:.1f}%")
                           
                            if illumination >= scene.min_illumination:
                                if not current_interval:
                                    print("  Deschid interval nou")
                                    current_interval = {
                                        'start_datetime': test_time,
                                        'elevation_min': elevation,
                                        'elevation_max': elevation,
                                        'azimuth_min': azimuth,
                                        'azimuth_max': azimuth,
                                        'illumination': illumination,
                                        'max_illumination': illumination
                                    }
                                else:
                                    current_interval['elevation_min'] = min(current_interval['elevation_min'], elevation)
                                    current_interval['elevation_max'] = max(current_interval['elevation_max'], elevation)
                                    current_interval['azimuth_min'] = min(current_interval['azimuth_min'], azimuth)
                                    current_interval['azimuth_max'] = max(current_interval['azimuth_max'], azimuth)
                                    current_interval['max_illumination'] = max(current_interval['max_illumination'], illumination)
                                    print("  Actualizez iluminare maximă în interval")
                            elif current_interval:
                                print("  Închid interval - iluminare insuficientă")
                                current_interval['end_datetime'] = test_time - timedelta(minutes=15)
                                if date_key not in daily_intervals:
                                    daily_intervals[date_key] = []
                                daily_intervals[date_key].append(current_interval)
                                current_interval = None
                                
                        except Exception as e:
                            print(f"!!! Eroare la verificarea iluminării: {e}")
                            if current_interval:
                                print("  Închid interval din cauza erorii")
                                current_interval['end_datetime'] = test_time - timedelta(minutes=15)
                                if date_key not in daily_intervals:
                                    daily_intervals[date_key] = []
                                daily_intervals[date_key].append(current_interval)
                                current_interval = None
                            continue
                        
                        # Actualizăm textul cu detalii mai specifice
                        progress.setLabelText(
                            f"Se analizează ziua {day + 1} din {days_to_check}\n"
                            f"Ora: {hour:02d}:{minute:02d}"
                        )
                
                print(f"Terminat ziua {day}")
                if current_interval:
                    print("Închid ultimul interval al zilei")
                    current_interval['end_datetime'] = test_time
                    if date_key not in daily_intervals:
                        daily_intervals[date_key] = []
                    daily_intervals[date_key].append(current_interval)
                    current_interval = None
            
            # Setăm progress la 100% pentru faza de procesare
            progress.setValue(100)
            progress.setLabelText("Se procesează intervalele găsite...")
            
            print("\nProcesare intervale găsite...")
            # Procesăm intervalele găsite
            consecutive_groups = []
            current_group = []
            previous_date = None
            
            for date in sorted(daily_intervals.keys()):
                print(f"Procesare data: {date}")
                if not previous_date or (date - previous_date).days == 1:
                    print("  Adaug la grupul curent")
                    current_group.extend(daily_intervals[date])
                else:
                    print("  Încep grup nou")
                    if current_group:
                        consecutive_groups.append(current_group)
                    current_group = daily_intervals[date]
                previous_date = date
            
            if current_group:
                consecutive_groups.append(current_group)
            
            print(f"\nGrupuri consecutive găsite: {len(consecutive_groups)}")
            
            # Pentru fiecare grup de zile consecutive, alegem intervalul cu iluminarea maximă
            selected_intervals = []
            for i, group in enumerate(consecutive_groups):
                print(f"\nProcesare grup {i+1}")
                best_interval = max(group, key=lambda x: x['max_illumination'])
                print(f"  Iluminare maximă în grup: {best_interval['max_illumination']:.1f}%")
                selected_intervals.append(best_interval)
            
            # Sortăm după dată și luăm primele num_opportunities intervale
            selected_intervals.sort(key=lambda x: x['start_datetime'])
            selected_intervals = selected_intervals[:num_opportunities]
            
            print(f"\nGăsite {len(selected_intervals)} intervale optime")
            scene.opportunities = selected_intervals
            scene.current_opportunity_index = 0
            self.parent.update_next_opportunity()  # Când se calculează oportunități noi
            
        except Exception as e:
            print(f"\n!!! EROARE CRITICĂ: {e}")
            import traceback
            traceback.print_exc()
        finally:
            progress.close()

    def is_time_in_window(self, time_str, start_str, end_str, ends_next_day):
        """Verifică dacă timpul dat este în fereastra permisă"""
        def time_to_minutes(t):
            h, m = map(int, t.split(':'))
            return h * 60 + m
            
        current = time_to_minutes(time_str)
        start = time_to_minutes(start_str)
        end = time_to_minutes(end_str)
        
        if ends_next_day:
            if end < start:
                end += 24 * 60
                if current < start:
                    current += 24 * 60
            return start <= current <= end
        else:
            return start <= current <= end

    def is_azimuth_in_range(self, azimuth, min_azimuth, max_azimuth):
        """
        Verifică dacă un azimut este în intervalul specificat, gestionând corect traversarea Nord-ului.
        
        Args:
            self: Instanța clasei
            azimuth (float): Azimutul de verificat (0-360)
            min_azimuth (float): Limita minimă a intervalului (0-360)
            max_azimuth (float): Limita maximă a intervalului (0-360)
            
        Returns:
            bool: True dacă azimutul este în interval, False altfel
        """
        # Normalizăm toate valorile la 0-360
        azimuth = azimuth % 360
        min_azimuth = min_azimuth % 360
        max_azimuth = max_azimuth % 360
        
        # Debug
        print(f"  DEBUG Azimuth check: {azimuth}° in range {min_azimuth}°-{max_azimuth}°")
        
        # Cazul normal: min < max (ex: 45° - 90°)
        if min_azimuth <= max_azimuth:
            return min_azimuth <= azimuth <= max_azimuth
        
        # Cazul special: min > max (ex: 330° - 30°) - traversează Nord
        # În acest caz, verificăm dacă azimutul este fie >= min SAU <= max
        return azimuth >= min_azimuth or azimuth <= max_azimuth

    def save_scenes(self):
        """Salvează scenele în fișier"""
        try:
            print("\n=== DEBUG save_scenes() ===")
            print(f"Salvare {len(self.scenes)} scene")
            
            data = {
                'scenes': [scene.to_dict() for scene in self.scenes]
            }
            # Salvăm cu backup
            backup_path = 'moon_scenes.json.bak'
            if os.path.exists('moon_scenes.json'):
                try:
                    import shutil
                    shutil.copy2('moon_scenes.json', backup_path)
                    print("Backup creat cu succes")
                except Exception as e:
                    print(f"Avertisment: Nu s-a putut crea backup: {e}")
            
            # Salvăm în fișier temporar mai întâi
            temp_path = 'moon_scenes.json.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                print(f"Date salvate în fișierul temporar: {temp_path}")
                    
            # Dacă salvarea a reușit, înlocuim fișierul original
            os.replace(temp_path, 'moon_scenes.json')
            print("Fișierul final creat cu succes")
                
        except Exception as e:
            print(f"!!! EROARE la salvarea scenelor: {e}")
            import traceback
            traceback.print_exc()

    def load_scenes(self):
        """Încarcă scenele din fișier fără a recalcula oportunitățile"""
        try:
            print("\n=== DEBUG load_scenes() ===")
            print(f"Încercare deschidere fișier moon_scenes.json")
            
            with open('moon_scenes.json', 'r') as f:
                data = json.load(f)
                raw_scenes = data.get('scenes', [])
                print(f"Fișier încărcat, {len(raw_scenes)} scene găsite")
                
                # Debug pentru fiecare scenă înainte de conversie
                for scene_data in raw_scenes:
                    print(f"\nScenă găsită în JSON: {scene_data.get('name')}")
                    print(f"  Număr oportunități în JSON: {len(scene_data.get('opportunities', []))}")
                    for opp in scene_data.get('opportunities', []):
                        print(f"  Oportunitate: start={opp.get('start_datetime')}, end={opp.get('end_datetime')}")
                        
            self.scenes = [Scene.from_dict(scene_data) for scene_data in raw_scenes]
            print(f"\nScene convertite: {len(self.scenes)}")
            
            # Verificare după conversie
            for scene in self.scenes:
                print(f"\nVerificare scenă convertită: {scene.name}")
                print(f"  Număr oportunități după conversie: {len(scene.opportunities)}")
                for opp in scene.opportunities:
                    print(f"  Oportunitate convertită: start={opp.get('start_datetime')}, end={opp.get('end_datetime')}")
                
            # Doar creăm widget-urile și actualizăm afișarea
            if self.scenes:
                print("\nCreare widgets pentru scene:")
                for scene in self.scenes:
                    print(f"  Creare widget pentru {scene.name}")
                    self.scenes_layout.addWidget(self.create_scene_widget(scene))
                
                print("\nActualizare next opportunity")
                self.parent.update_next_opportunity()
                                
        except FileNotFoundError:
            print("Nu s-a găsit fișierul de scene. Se va crea la prima salvare.")
            self.scenes = []
        except json.JSONDecodeError:
            print("Fișierul de scene este corupt. Se va crea unul nou.")
            self.scenes = []
        except Exception as e:
            print(f"Eroare la încărcarea scenelor: {e}")
            import traceback
            traceback.print_exc()
            self.scenes = []

class MoonPhaseWindow(QMainWindow):
    def log_event(self, category, message, is_error=False, level='INFO'):
        """Helper pentru logging consistent, cu nivel de detaliu controlabil"""
        if not hasattr(self, 'last_log'):
            self.last_log = {}
            self.log_level = 'INFO'  # Poți seta la 'DEBUG' când ai nevoie de mai multe detalii
        
        # Evităm duplicarea mesajelor identice consecutive
        if self.last_log.get(category) == message:
            return
            
        self.last_log[category] = message
        
        # Controlăm ce se afișează bazat pe nivel
        if level == 'DEBUG' and self.log_level != 'DEBUG':
            return
            
        # Formatare consistentă și simplificată
        if is_error:
            print(f"\n!!! EROARE {category}: {message}")
        elif level == 'DEBUG':
            print(f"DEBUG {category}: {message}")
        else:
            print(f"\n=== {category}: {message}")

    def __init__(self):
        super().__init__()
        # Adăugăm ProfileManager la inițializare
        self.profile_manager = ProfileManager()
        self.log_event("INIȚIALIZARE", "Pornire aplicație Moon Hunter")
       
        self.tf = TimezoneFinder()
        self.current_timezone = pytz.timezone('Europe/Bucharest')  # timezone implicit
        self.setWindowTitle("Moon Hunter")
        self.setMinimumSize(800, 600)  # Reducem înălțimea minimă
       
        self.log_event("SISTEM", "Inițializare DataManager")
        self.data_manager = MeteoDataManager()
        self.settings = self.load_settings()
       
        if self.settings.get('window_size'):
            self.resize(self.settings['window_size'][0], self.settings['window_size'][1])
        if self.settings.get('window_position'):
            self.move(self.settings['window_position'][0], self.settings['window_position'][1])
       
        self.log_event("SISTEM", "Încărcare date astronomice")
        self.ts = load.timescale()
        self.eph = load('de421.bsp')
        self.location = Topos('44.4268 N', '26.1025 E')
       
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        layout.setSpacing(1)  # Reducem spacing-ul între elemente
        layout.setContentsMargins(10, 3, 10, 3)  # Reducem marginile
        main_widget.setLayout(layout)

        # === ROW 1: Informatii timp + Selectare locatie + Coordonate GPS ===
        self.log_event("UI", "Creare containere principale")
        top_container = QWidget()
        top_layout = QHBoxLayout()
        top_layout.setSpacing(2)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_container.setLayout(top_layout)

        # --- PRIMUL GRUP: Informatii Timp ---
        self.log_event("UI", "Creare grup informații timp")
        time_group = QGroupBox("Informații Timp")
        time_layout = QVBoxLayout()
        time_layout.setSpacing(3)
       
        self.current_time_label = QLabel()
        self.current_time_label.setStyleSheet("font-size: 20px;")
        self.current_time_label.setWordWrap(True)
        
        self.moonrise_time_label = QLabel()
        self.moonrise_time_label.setStyleSheet("font-size: 20px;")
        self.moonrise_time_label.setWordWrap(True)
       
        time_layout.addWidget(self.current_time_label)
        time_layout.addWidget(self.moonrise_time_label)
        time_group.setLayout(time_layout)

        # --- AL DOILEA GRUP: Selectare Locatie ---
        self.log_event("UI", "Creare interfață selecție locație")
        location_group = QGroupBox("Selectare Locație")
        location_layout = QGridLayout()
        location_layout.setVerticalSpacing(3)

        self.judet_combo = QComboBox()
        self.localitate_combo = QComboBox()
        judet_label = QLabel("Județ:")
        localitate_label = QLabel("Localitate:")
        self.hide_comune_checkbox = QCheckBox("Ascunde comunele")
        self.hide_comune_checkbox.setChecked(self.settings.get('hide_comune', False))
        self.hide_comune_checkbox.stateChanged.connect(self.on_hide_comune_changed)
        update_location_button = QPushButton("Actualizează Locația")
        update_location_button.clicked.connect(self.update_location_from_combos)

        location_layout.addWidget(judet_label, 0, 0)
        location_layout.addWidget(self.judet_combo, 0, 1)
        location_layout.addWidget(self.hide_comune_checkbox, 0, 2, 1, 2)

        location_layout.addWidget(localitate_label, 1, 0)
        location_layout.addWidget(self.localitate_combo, 1, 1)
        location_layout.addWidget(update_location_button, 1, 2, 1, 2)

        location_group.setLayout(location_layout)

        self.log_event("DATE", "Populare listă județe")
        judete = self.data_manager.get_judete()
        self.judet_combo.addItems(judete)

        last_judet = self.settings.get('last_judet', 'Alba')
        if last_judet in [self.judet_combo.itemText(i) for i in range(self.judet_combo.count())]:
            self.judet_combo.setCurrentText(last_judet)
        else:
            self.judet_combo.setCurrentIndex(0)

        self.judet_combo.currentTextChanged.connect(self.update_localitati)
        self.update_localitati(self.judet_combo.currentText())

        # --- AL TREILEA GRUP: Coordonate GPS ---
        self.log_event("UI", "Creare interfață GPS și profile")
        gps_group = QGroupBox("Coordonate GPS")
        gps_layout = QVBoxLayout()
        gps_layout.setSpacing(3)

        # Container pentru coordonate
        coords_container = QWidget()
        coords_layout = QHBoxLayout()

        self.gps_input = QLineEdit()
        self.gps_input.setPlaceholderText("ex: 46.2746751 23.0650287")
        self.gps_input.returnPressed.connect(self.update_location_from_gps)

        gps_btn = QPushButton("Actualizează cu GPS")
        gps_btn.clicked.connect(self.update_location_from_gps)

        coords_layout.addWidget(self.gps_input)
        coords_layout.addWidget(gps_btn)
        coords_container.setLayout(coords_layout)
       
        # Container pentru numele profilului
        profile_name_container = QWidget()
        profile_name_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.update_profile_list()
        profile_name_layout.addWidget(self.profile_combo)
        profile_name_container.setLayout(profile_name_layout)

        # Container pentru butoane
        profile_buttons_container = QWidget()
        profile_buttons_layout = QHBoxLayout()

        save_btn = QPushButton("Salvează Locația")
        save_btn.clicked.connect(self.save_current_location)

        load_btn = QPushButton("Încarcă Locația")
        load_btn.clicked.connect(self.load_selected_profile)

        delete_btn = QPushButton("Șterge") 
        delete_btn.clicked.connect(self.delete_selected_profile)

        profile_buttons_layout.addWidget(save_btn)
        profile_buttons_layout.addWidget(load_btn)
        profile_buttons_layout.addWidget(delete_btn)
        profile_buttons_container.setLayout(profile_buttons_layout)

        # Adăugăm cele trei containere în layout-ul principal al grupului GPS
        gps_layout.addWidget(coords_container)
        gps_layout.addWidget(profile_name_container)
        gps_layout.addWidget(profile_buttons_container)

        gps_group.setLayout(gps_layout)

        # Adăugăm toate cele trei grupuri pe primul rând
        top_layout.addWidget(time_group, 1)
        top_layout.addWidget(location_group, 1)
        top_layout.addWidget(gps_group, 1)

        # Adăugăm primul rând la layout-ul principal
        layout.addWidget(top_container)

        # === ROW 2: Fotografii + Pozitia Lunii ===
        self.log_event("UI", "Creare interfață poziție lună")
        mid_container = QWidget()
        mid_layout = QHBoxLayout()
        mid_layout.setSpacing(2)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_container.setLayout(mid_layout)

        # --- Primul grup: Faza Lunii (panel fotografii) ---
        moon_group = QGroupBox("Faza Lunii")
        moon_layout = QHBoxLayout()
        moon_layout.setSpacing(3)
        moon_layout.setContentsMargins(5, 0, 5, 0)  # Reduce margins
       
        # Container stânga pentru compas și informații poziție
        left_container = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(3)

        self.compass_widget = CompassWidget()
        self.compass_widget.setFixedSize(384, 384)
        left_layout.addWidget(self.compass_widget, alignment=Qt.AlignCenter)
       
        self.compass_info_label = QLabel()
        self.compass_info_label.setStyleSheet("font-size: 16px; color: white;")
        self.compass_info_label.setWordWrap(True)
        self.compass_info_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.compass_info_label)
       
        left_container.setLayout(left_layout)
       
        # Container dreapta pentru imagine lună și text
        right_container = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setSpacing(3)
       
        # Widget-uri pentru imagine
        image_container = QWidget()
        image_layout = QVBoxLayout()
        image_layout.setContentsMargins(0, 0, 0, 0)
        image_layout.setSpacing(3)
       
        self.moon_image = QLabel()
        self.moon_image.setAlignment(Qt.AlignCenter)
        self.moon_image.setFixedSize(384, 384)
        self.moon_image.setScaledContents(False)
        self.moon_image.setStyleSheet("""
            QLabel {
                background-color: #2b2b2b;
                padding: 0px;
                margin: 0px;
            }
        """)
        image_layout.addWidget(self.moon_image, alignment=Qt.AlignCenter)
        image_container.setLayout(image_layout)
       
        # Widget-uri pentru text
        text_container = QWidget()
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(3)
       
        self.phase_label = QLabel()
        self.phase_label.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        self.phase_label.setWordWrap(True)
       
        self.age_label = QLabel()
        self.age_label.setStyleSheet("font-size: 14px; color: white;")
       
        self.image_name_label = QLabel()
        self.image_name_label.setStyleSheet("font-size: 10px; color: #808080;")
       
        text_layout.addWidget(self.phase_label)
        text_layout.addWidget(self.age_label)
        text_layout.addWidget(self.image_name_label)
        text_container.setLayout(text_layout)
       
        right_layout.addWidget(image_container)
        right_layout.addWidget(text_container)
        right_container.setLayout(right_layout)
       
        moon_layout.addWidget(left_container)
        moon_layout.addWidget(right_container)
        moon_group.setLayout(moon_layout)

        # --- Al doilea grup: Poziția Lunii ---
        pos_group = QGroupBox("Poziția Lunii")
        pos_layout = QVBoxLayout()
        pos_layout.setSpacing(3)
       
        self.elevation_label = QLabel()
        self.elevation_label.setStyleSheet("font-size: 16px;")
        self.elevation_label.setAlignment(Qt.AlignCenter)
        
        self.azimuth_label = QLabel()
        self.azimuth_label.setStyleSheet("font-size: 16px;")
        self.azimuth_label.setAlignment(Qt.AlignCenter)
        
        # Adăugăm labels pentru distanță
        self.distance_label = QLabel()
        self.distance_label.setStyleSheet("font-size: 16px;")
        self.distance_label.setAlignment(Qt.AlignCenter)
        
        self.distance_progress_label = QLabel()
        self.distance_progress_label.setTextFormat(Qt.RichText)
        self.distance_progress_label.setAlignment(Qt.AlignCenter)

        # Reducem spacing-ul între widget-uri dar nu prea mult (apropiat de 1.5)
        pos_layout.setSpacing(8)
        
        # Adăugăm un stretch la început și la sfârșit pentru a centra vertical conținutul
        pos_layout.addStretch(1)
        pos_layout.addWidget(self.elevation_label)
        pos_layout.addWidget(self.azimuth_label)
        pos_layout.addWidget(self.distance_label)
        pos_layout.addWidget(self.distance_progress_label)
        pos_layout.addStretch(1)

        pos_group.setLayout(pos_layout)

        # Adăugăm grupurile la al doilea rând
        mid_layout.addWidget(moon_group, 5)
        mid_layout.addWidget(pos_group, 1)
        
        # Adăugăm al doilea rând la layout-ul principal
        layout.addWidget(mid_container)

        # === ROW 3: Time Shift + Următoarea Oportunitate + Scene Editor ===
        bottom_container = QWidget()
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(2)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_container.setLayout(bottom_layout)

        # --- Time Shift ---
        self.timeshift_widget = TimeshiftWidget(self)

        # --- Următoarea Oportunitate ---
        next_opportunity_group = QGroupBox("Următoarea Oportunitate")
        next_opportunity_layout = QHBoxLayout()
        self.next_opportunity_label = QLabel("Nu există oportunități viitoare")
        self.next_opportunity_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                padding: 5px;
            }
        """)
        self.next_opportunity_label.setAlignment(Qt.AlignCenter)
        next_opportunity_layout.addWidget(self.next_opportunity_label)
        
        # Butonul "Rating luni pline"
        self.full_moon_btn = QPushButton("Rating luni pline")
        self.full_moon_btn.clicked.connect(self.show_full_moon_ratings)
        next_opportunity_layout.addWidget(self.full_moon_btn)
        next_opportunity_group.setLayout(next_opportunity_layout)

        # --- Scene Editor button ---
        scene_editor_container = QWidget()
        scene_editor_layout = QVBoxLayout()
        self.scene_editor_btn = QPushButton("Scene Editor")
        self.scene_editor_btn.clicked.connect(self.open_scene_editor)
        self.scene_editor_btn.setFixedHeight(60)  # Make button taller to match other elements
        self.scene_editor_btn.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
            }
        """)
        scene_editor_layout.addWidget(self.scene_editor_btn)
        scene_editor_container.setLayout(scene_editor_layout)

        # Adăugăm cele trei elemente la al treilea rând
        bottom_layout.addWidget(self.timeshift_widget, 5)
        bottom_layout.addWidget(next_opportunity_group, 4)
        bottom_layout.addWidget(scene_editor_container, 1)

        # Adăugăm al treilea rând la layout-ul principal
        layout.addWidget(bottom_container)

        # Footer cu nume autor
        self.author_label = QLabel("Mihai Mereu")
        self.author_label.setStyleSheet("""
            QLabel {
                color: #808080;
                font-size: 12px;
                padding: 0px;
                margin: 0px;
            }
        """)
        self.author_label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.author_label.setFixedHeight(15)
        layout.addWidget(self.author_label, 0, Qt.AlignRight)
        layout.setContentsMargins(10, 5, 10, 0)

        # Setăm stylesheet-ul pentru aplicație
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #2b2b2b;
            }
            QGroupBox {
                border: 2px solid #404040;
                border-radius: 6px;
                margin-top: 3px;
                padding-top: 3px;
                color: white;
                font-size: 13px;
                font-weight: bold;
            }
            QLabel, QCheckBox {
                color: white;
                font-size: 13px;
            }
            QComboBox, QLineEdit {
                background-color: #404040;
                color: white;
                border: 1px solid #505050;
                border-radius: 4px;
                padding: 3px 5px;
                min-height: 25px;
                font-size: 13px;
            }
            QPushButton {
                background-color: #0d47a1;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 3px 15px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
        """)

        # Configurare timer și inițializare
        self.log_event("SISTEM", "Configurare timer")
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_all)
        self.timer.start(1000)

        # Restaurare stare aplicație și inițializare scene editor
        self.log_event("RESTAURARE", "Restaurare stare aplicație")
        self.restore_application_state()
        
        print("\n=== INIȚIALIZARE SCENE EDITOR LA PORNIRE ===")
        self.scene_editor_window = SceneEditorWindow(self)
        self.update_next_opportunity()

    def restore_application_state(self):
        """Restaurează starea aplicației la pornire"""
        # 1. Mai întâi restaurăm profilurile în combo
        if 'profiles' in self.settings:
            self.profile_manager.profiles = {
                name: LocationProfile.from_dict(profile_data)
                for name, profile_data in self.settings['profiles'].items()
            }
            self.update_profile_list()

        # 2. Restaurăm selecția românească în combo-uri
        if 'romania_view' in self.settings:
            saved_judet = self.settings['romania_view']['judet']
            saved_localitate = self.settings['romania_view']['localitate']
            if saved_judet:
                self.log_event("RESTAURARE", f"Restaurare selecție: {saved_localitate}, {saved_judet}")
                self.judet_combo.setCurrentText(saved_judet)
                self.update_localitati(saved_judet)
                if saved_localitate:
                    self.localitate_combo.setCurrentText(saved_localitate)

        # 3. Restaurăm selecția de profil în combo
        if 'profile_view' in self.settings and self.settings['profile_view']:
            saved_profile = self.settings['profile_view']
            self.log_event("RESTAURARE", f"Restaurare profil: {saved_profile}")
            self.profile_combo.setCurrentText(saved_profile)

        # 4. Așteptăm să se termine toate restaurările de combo-uri
        self.update_moon_data(silent=True)

        # 5. Activăm view-ul care era activ ultima oară
        active_view = self.settings.get('active_view', 'romania')
        self.log_event("RESTAURARE", f"Activare vizualizare: {active_view}")

        if active_view == 'romania':
            self.update_location_from_combos()
        elif active_view == 'profile' and self.settings.get('profile_view'):
            self.load_selected_profile()

        self.print_moon_status()

    def open_scene_editor(self):
        """Deschide fereastra Scene Editor"""
        if not hasattr(self, 'scene_editor_window'):
            print("\n=== INIȚIALIZARE SCENE EDITOR ===")
            self.scene_editor_window = SceneEditorWindow(self)
            # Asigurăm că s-au încărcat scenele înainte să actualizăm oportunitatea
            print("Actualizare next opportunity după încărcare scene")
            self.update_next_opportunity()
        self.scene_editor_window.show()

    def show_full_moon_ratings(self):
        """Deschide dialogul cu rating-uri"""
        dialog = FullMoonDialog(self)
        # Centrăm dialogul relativ la fereastra principală
        dialog.setGeometry(
            self.x() + (self.width() - dialog.width()) // 2,
            self.y() + (self.height() - dialog.height()) // 2,
            dialog.width(),
            dialog.height()
        )
        dialog.exec_()

    def update_next_opportunity(self):
        """Actualizează informațiile despre următoarele 3 oportunități"""
        if not hasattr(self, 'scene_editor_window') or not self.scene_editor_window:
            self.next_opportunity_label.setText("Scene Editor nu este inițializat")
            return
            
        # Colectăm toate oportunitățile din toate scenele
        all_opportunities = []
        current_time = datetime.now(self.current_timezone)
        
        for scene in self.scene_editor_window.scenes:
            for opp in scene.opportunities:
                opp_start = opp['start_datetime']
                if opp_start > current_time:
                    # Calculăm ratingul de distanță pentru momentul oportunității
                    ts = self.ts.from_datetime(opp_start)
                    distance_info = self.calculate_moon_distance_at(ts)
                    
                    # Calculăm iluminarea pentru momentul oportunității
                    timestamp = int(opp_start.timestamp())
                    try:
                        response = requests.get(f'https://api.farmsense.net/v1/moonphases/?d={timestamp}')
                        moon_data = response.json()[0]
                        illumination = float(moon_data['Illumination']) * 100
                    except Exception as e:
                        print(f"Eroare la obținerea iluminării: {e}")
                        illumination = None
                    
                    all_opportunities.append({
                        'scene_name': scene.name,
                        'start_datetime': opp_start,
                        'distance_info': distance_info,
                        'illumination': illumination
                    })
        
        # Sortăm toate oportunitățile după timp
        all_opportunities.sort(key=lambda x: x['start_datetime'])
        
        # Luăm primele 3
        next_opps = all_opportunities[:3]
        
        if next_opps:
            # Creăm text pentru fiecare oportunitate pe un singur rând
            lines = []
            for i, opp in enumerate(next_opps, 1):
                # Formatăm distanța și rating
                distance_str = ""
                if opp['distance_info']:
                    status_parts = opp['distance_info']['status'].split()
                    rating_part = status_parts[-1]  # (X/10)
                    status_name = status_parts[0]   # APOGEU/PERIGEU/INTERMEDIAR
                    distance_str = f" • {status_name} {rating_part}"
                    
                # Adăugăm iluminarea rotunjită la întreg
                illumination_str = ""
                if opp['illumination'] is not None:
                    illumination_str = f" • {round(opp['illumination'])}% iluminare"
                    
                line = f"#{i}: {opp['scene_name']} • {opp['start_datetime'].strftime('%d/%m/%Y %H:%M')}{distance_str}{illumination_str}"
                lines.append(line)
                
            final_text = "\n".join(lines)
            self.next_opportunity_label.setText(final_text)
            
        else:
            self.next_opportunity_label.setText("Nu există oportunități viitoare")

    def notify_location_change(self):
        """
        Notifică Scene Editor că locația s-a schimbat, dar nu mai recalculează automat
        """
        if hasattr(self, 'scene_editor_window'):
            # Doar actualizăm afișarea cu datele existente
            for i in reversed(range(self.scene_editor_window.scenes_layout.count())):
                widget = self.scene_editor_window.scenes_layout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)
            for scene in self.scene_editor_window.scenes:
                self.scene_editor_window.scenes_layout.addWidget(
                    self.scene_editor_window.create_scene_widget(scene))
                
    def load_settings(self):
        """Încarcă setările din fișier sau creează unele implicite dacă nu există."""
        default_settings = {
            'window_size': [800, 900],
            'window_position': [100, 100],
            'hide_comune': False,
            'romania_view': {
                'judet': 'Alba',
                'localitate': 'Alba Iulia'
            },
            'profile_view': '',
            'active_view': 'romania',
            'profiles': {}
        }
        
        try:
            # Încercăm să citim setările existente
            with open('moon_settings.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # Ne asigurăm că toate cheile necesare există
                for key, value in default_settings.items():
                    if key not in data:
                        data[key] = value
                
                # Încărcăm profilurile dacă există
                if 'profiles' in data:
                    self.profile_manager.profiles = {
                        name: LocationProfile.from_dict(profile_data)
                        for name, profile_data in data['profiles'].items()
                    }
                
                return data
                
        except FileNotFoundError:
            print("Nu s-a găsit fișierul de setări. Se creează unul nou cu valori implicite...")
            # Creăm fișierul cu setări implicite
            with open('moon_settings.json', 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, indent=4, ensure_ascii=False)
            return default_settings
        except json.JSONDecodeError:
            print("Fișierul de setări este corupt. Se creează unul nou cu valori implicite...")
            with open('moon_settings.json', 'w', encoding='utf-8') as f:
                json.dump(default_settings, f, indent=4, ensure_ascii=False)
            return default_settings
        except Exception as e:
            print(f"Eroare la încărcarea setărilor: {e}")
            return default_settings

    def save_settings(self, silent=False):
        """Salvează setările"""
        settings = {
            'window_size': [self.width(), self.height()],
            'window_position': [self.x(), self.y()],
            'hide_comune': self.hide_comune_checkbox.isChecked(),
            'romania_view': {
                'judet': self.judet_combo.currentText(),
                'localitate': self.localitate_combo.currentText()
            },
            'profile_view': self.profile_combo.currentText(),
            'active_view': self.settings.get('active_view', 'romania'),
            'profiles': {
                name: profile.to_dict()
                for name, profile in self.profile_manager.profiles.items()
            }
        }
        
        try:
            with open('moon_settings.json', 'w') as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            if not silent:
                self.log_event("SALVARE SETĂRI", str(e), is_error=True)

    def save_last_profile(self, profile_name):
        """Salvează ultimul profil folosit"""
        try:
            with open(self.profile_manager.settings_file, 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        
        data['last_profile'] = profile_name
        
        with open(self.profile_manager.settings_file, 'w') as f:
            json.dump(data, f, indent=4)

    def load_last_profile(self):
        """Încarcă ultimul profil folosit."""
        try:
            with open(self.profile_manager.settings_file, 'r') as f:
                data = json.load(f)
                last_profile = data.get('last_profile')
                if last_profile and last_profile in self.profile_manager.get_all_profiles():
                    self.profile_combo.setCurrentText(last_profile)
                    self.load_selected_profile()
        except (FileNotFoundError, json.JSONDecodeError):
            print("Nu s-a putut încărca ultimul profil folosit.")
        except Exception as e:
            print(f"Eroare la încărcarea ultimului profil: {e}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.save_settings()

    def moveEvent(self, event):
        super().moveEvent(event)
        self.save_settings()

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

    def update_localitati(self, judet):
        """Actualizează lista de localități când se schimbă județul"""
        current_loc = self.localitate_combo.currentText()
        self.localitate_combo.clear()
        
        hide_comune = self.hide_comune_checkbox.isChecked()
        localitati = self.data_manager.get_localitati(judet, hide_comune)
        
        self.log_event("LOCALITĂȚI", 
                       f"Actualizare {judet}: {len(localitati)} localități găsite",
                       level='DEBUG')
        
        self.localitate_combo.addItems(localitati)
        
        if current_loc in localitati:
            self.localitate_combo.setCurrentText(current_loc)
        else:
            self.localitate_combo.setCurrentIndex(0)

    def on_hide_comune_changed(self, state):
        """Handler pentru schimbarea stării checkbox-ului de ascundere comune"""
        print(f"\n=== DEBUG ON_HIDE_COMUNE_CHANGED ===")
        print(f"Stare nouă checkbox: {state}")
        self.update_localitati(self.judet_combo.currentText())
        self.save_settings()

    def update_location_from_combos(self):
        """Actualizează locația folosind selecția din combo-uri pentru România și resetează la timpul prezent"""
        judet = self.judet_combo.currentText()
        localitate = self.localitate_combo.currentText()
        
        lat, lon = self.data_manager.get_coordinates(judet, localitate)
        if lat and lon:
            # Resetăm timeshift-ul dacă există
            if hasattr(self, 'timeshift_datetime'):
                delattr(self, 'timeshift_datetime')
            if hasattr(self, 'timeshift_ts'):
                delattr(self, 'timeshift_ts')
                
            self.location = Topos(f'{lat} N', f'{lon} E')
            self.current_timezone = pytz.timezone('Europe/Bucharest')
            
            # Reset stylesheet la original - ADAUGĂ AICI
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #2b2b2b;
                }
                QGroupBox {
                    border: 2px solid #404040;
                    border-radius: 6px;
                    margin-top: 12px;
                    padding-top: 10px;
                    color: white;
                    font-size: 13px;
                    font-weight: bold;
                }
                QLabel, QCheckBox {
                    color: white;
                    font-size: 13px;
                }
                QComboBox, QLineEdit {
                    background-color: #404040;
                    color: white;
                    border: 1px solid #505050;
                    border-radius: 4px;
                    padding: 5px;
                    min-height: 25px;
                    font-size: 13px;
                }
                QPushButton {
                    background-color: #0d47a1;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 15px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #1565c0;
                }
            """)
            
            self.log_event("ACTUALIZARE LOCAȚIE", 
                          f"Locație: {localitate}, {judet}\n"
                          f"Coordonate: {lat}°N, {lon}°E\n"
                          f"Timezone: Europe/Bucharest")
            
            self.settings['active_view'] = 'romania'
            self.save_settings(silent=True)
            
            self.update_moon_data()
            self.print_moon_status()

            self.notify_location_change()

    def update_location_from_gps(self):
        """Actualizează locația din coordonate GPS și resetează la timpul prezent"""
        try:
            coords_input = self.gps_input.text().strip().replace(',', ' ')
            coords = [x for x in coords_input.split(' ') if x]
            
            if len(coords) != 2:
                self.log_event("VALIDARE GPS", 
                              "Format așteptat: latitudine longitudine\n"
                              "Exemple:\n"
                              "  46.2746751 23.0650287\n"
                              "  46.2746751, 23.0650287", 
                              is_error=True)
                return
            
            lat = float(coords[0])
            lon = float(coords[1])
            
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                self.log_event("VALIDARE GPS",
                              "Limite valide:\n"
                              "  Latitudine: -90° până la +90°\n"
                              "  Longitudine: -180° până la +180°",
                              is_error=True)
                return
            
            # Resetăm timeshift-ul dacă există
            if hasattr(self, 'timeshift_datetime'):
                delattr(self, 'timeshift_datetime')
            if hasattr(self, 'timeshift_ts'):
                delattr(self, 'timeshift_ts')
                
            # Reset stylesheet la original - ADAUGĂ AICI
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #2b2b2b;
                }
                QGroupBox {
                    border: 2px solid #404040;
                    border-radius: 6px;
                    margin-top: 12px;
                    padding-top: 10px;
                    color: white;
                    font-size: 13px;
                    font-weight: bold;
                }
                QLabel, QCheckBox {
                    color: white;
                    font-size: 13px;
                }
                QComboBox, QLineEdit {
                    background-color: #404040;
                    color: white;
                    border: 1px solid #505050;
                    border-radius: 4px;
                    padding: 5px;
                    min-height: 25px;
                    font-size: 13px;
                }
                QPushButton {
                    background-color: #0d47a1;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 15px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #1565c0;
                }
            """)
            
            self.location = Topos(f'{lat} N', f'{lon} E')
            self.update_timezone_from_coordinates(lat, lon)
            
            self.log_event("ACTUALIZARE GPS",
                          f"Coordonate: {lat}°N, {lon}°E")
            
            self.settings['active_view'] = 'gps'
            self.save_settings(silent=True)
            
            self.update_moon_data()
            self.print_moon_status()

            self.notify_location_change()
            
        except ValueError as e:
            self.log_event("EROARE GPS", 
                          "Coordonatele trebuie să fie numere valide",
                          is_error=True)

    def update_timezone_from_coordinates(self, lat, lon):
        """Actualizează fusul orar bazat pe coordonatele GPS"""
        try:
            timezone_str = self.tf.timezone_at(lat=lat, lng=lon)
            if timezone_str:
                self.current_timezone = pytz.timezone(timezone_str)
                local_time = datetime.now(self.current_timezone)
                print(f"\n=== ACTUALIZARE FUS ORAR ===")
                print(f"Coordonate: {lat}°N, {lon}°E")
                print(f"Fus orar detectat: {timezone_str}")
                print(f"Ora locală: {local_time.strftime('%H:%M:%S')}")
                print(f"Offset UTC: {local_time.strftime('%z')}")
                print("=" * 25)
                
                # Actualizăm imediat toate afișările de timp
                self.update_moon_data()
            else:
                print(f"\n!!! AVERTISMENT: Nu s-a putut detecta fusul orar pentru coordonatele {lat}, {lon} !!!")
                # Setăm un fus orar implicit bazat pe longitudine
                hours_offset = round(lon / 15)
                if hours_offset > 0:
                    timezone_str = f"Etc/GMT-{hours_offset}"
                else:
                    timezone_str = f"Etc/GMT+{abs(hours_offset)}"
                self.current_timezone = pytz.timezone(timezone_str)
                print(f"S-a setat fusul orar aproximativ: {timezone_str}")
        except Exception as e:
            print(f"\n!!! EROARE la actualizarea fusului orar: {e} !!!")
            # În caz de eroare, setăm fusul orar la UTC
            self.current_timezone = pytz.UTC
            print("S-a setat fusul orar la UTC")

    def suggest_location_name(self, lat, lon):
        """Sugerează un nume pentru locație bazat pe coordonate"""
        try:
            from geopy.geocoders import Nominatim
            geolocator = Nominatim(user_agent="moonhunter")
            location = geolocator.reverse(f"{lat}, {lon}")
            
            if location:
                address = location.raw.get('address', {})
                # Încercăm să găsim cel mai specific nume
                for key in ['city', 'town', 'village', 'suburb', 'county', 'state']:
                    if key in address:
                        return address[key]
            return f"Locație {lat:.2f}, {lon:.2f}"
        except Exception as e:
            print(f"Eroare la sugerarea numelui locației: {e}")
            return f"Locație {lat:.2f}, {lon:.2f}"

    def save_current_location(self):
        """Salvează locația curentă ca profil"""
        try:
            # Determinăm sursa coordonatelor în funcție de active_view
            if self.settings.get('active_view') == 'romania':
                judet = self.judet_combo.currentText()
                localitate = self.localitate_combo.currentText()
                lat, lon = self.data_manager.get_coordinates(judet, localitate)
                suggested_name = f"{localitate}, {judet}"
            else:
                coords = self.gps_input.text().strip().split()
                if len(coords) != 2:
                    print("\n!!! EROARE: Coordonate invalide !!!\n")
                    return
                lat = float(coords[0])
                lon = float(coords[1])
                suggested_name = self.suggest_location_name(lat, lon)
            
            # Dialog pentru nume profil
            from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel
            
            dialog = QDialog(self)
            dialog.setWindowTitle("Salvare Profil")
            layout = QVBoxLayout()
            
            layout.addWidget(QLabel("Nume profil:"))
            name_input = QLineEdit(suggested_name)
            layout.addWidget(name_input)
            
            buttons = QDialogButtonBox(
                QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
                Qt.Horizontal
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            
            dialog.setLayout(layout)
            
            if dialog.exec_() == QDialog.Accepted:
                profile_name = name_input.text().strip()
                if profile_name:
                    # Creăm și salvăm profilul
                    profile = LocationProfile(
                        profile_name, lat, lon,
                        self.current_timezone.zone if hasattr(self, 'current_timezone') else None
                    )
                    self.profile_manager.add_profile(profile)
                    self.update_profile_list()
                    self.profile_combo.setCurrentText(profile_name)
                    
                    print(f"\n=== SALVARE PROFIL ===")
                    print(f"Nume: {profile_name}")
                    print(f"Coordonate: {lat}°N, {lon}°E")
                    print(f"Timezone: {profile.timezone}")
                    
                    # Salvăm și ca ultima locație folosită
                    self.save_last_profile(profile_name)
                    
        except Exception as e:
            print(f"\n!!! EROARE la salvarea profilului: {e} !!!\n")

    def load_selected_profile(self):
        """Încarcă profilul selectat și resetează la timpul prezent"""
        profile_name = self.profile_combo.currentText()
        if not profile_name:
            self.log_event("PROFIL", "Nu este selectat niciun profil", is_error=True)
            return
                
        profile = self.profile_manager.get_profile(profile_name)
        if profile:
            # Resetăm timeshift-ul dacă există
            if hasattr(self, 'timeshift_datetime'):
                delattr(self, 'timeshift_datetime')
            if hasattr(self, 'timeshift_ts'):
                delattr(self, 'timeshift_ts')
            
            # Reset stylesheet la original - ADAUGĂ AICI
            self.setStyleSheet("""
                QMainWindow, QWidget {
                    background-color: #2b2b2b;
                }
                QGroupBox {
                    border: 2px solid #404040;
                    border-radius: 6px;
                    margin-top: 12px;
                    padding-top: 10px;
                    color: white;
                    font-size: 13px;
                    font-weight: bold;
                }
                QLabel, QCheckBox {
                    color: white;
                    font-size: 13px;
                }
                QComboBox, QLineEdit {
                    background-color: #404040;
                    color: white;
                    border: 1px solid #505050;
                    border-radius: 4px;
                    padding: 5px;
                    min-height: 25px;
                    font-size: 13px;
                }
                QPushButton {
                    background-color: #0d47a1;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 15px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #1565c0;
                }
            """)
            
            self.log_event("ACTIVARE PROFIL",
                          f"Nume: {profile_name}\n"
                          f"Coordonate: {profile.latitude}°N, {profile.longitude}°E")
            
            self.location = Topos(f'{profile.latitude} N', f'{profile.longitude} E')
            
            if profile.timezone:
                try:
                    self.current_timezone = pytz.timezone(profile.timezone)
                    print(f"Fus orar: {profile.timezone}")
                except:
                    self.update_timezone_from_coordinates(profile.latitude, profile.longitude)
            else:
                self.update_timezone_from_coordinates(profile.latitude, profile.longitude)
            
            self.gps_input.setText(f"{profile.latitude} {profile.longitude}")
            self.settings['active_view'] = 'profile'
            self.save_settings(silent=True)
            
            self.update_moon_data()
            self.print_moon_status()

            self.notify_location_change()
        else:
            self.log_event("PROFIL", 
                          f"Profilul '{profile_name}' nu există",
                          is_error=True)

    def delete_selected_profile(self):
        """Șterge profilul selectat"""
        profile_name = self.profile_combo.currentText()
        if not profile_name:
            return
            
        self.profile_manager.remove_profile(profile_name)
        self.update_profile_list()

    def update_profile_list(self):
        """Actualizează lista de profile din combobox"""
        current_text = self.profile_combo.currentText()
        self.profile_combo.clear()
        self.profile_combo.addItems(self.profile_manager.get_all_profiles())
        if current_text and current_text in self.profile_manager.get_all_profiles():
            self.profile_combo.setCurrentText(current_text)

    def apply_timeshift(self, target_datetime):
        try:
            print("\n" + "=" * 50)
            print(f"APLICARE TIMESHIFT LA: {target_datetime.strftime('%Y-%m-%d %H:%M')}")
            
            self.timeshift_datetime = target_datetime.astimezone(self.current_timezone)
            self.timeshift_ts = self.ts.from_datetime(self.timeshift_datetime)
            
            self.update_moon_data()
            self.update_all()
            
            # Forțăm un print complet al statusului după timeshift
            self.print_moon_status()  
            
        except Exception as e:
            print(f"\n!!! EROARE la aplicarea timeshift: {e} !!!\n")
            raise
            
    def calculate_moon_position(self):
        """Calculate current moon elevation and azimuth"""
        try:
            # Folosim timpul din timeshift dacă există
            time_ref = self.timeshift_ts if hasattr(self, 'timeshift_ts') else self.ts.now()
            
            earth = self.eph['earth']
            moon = self.eph['moon']
            astrometric = (earth + self.location).at(time_ref).observe(moon)
            alt, az, _ = astrometric.apparent().altaz()
            return alt.degrees, az.degrees
        except Exception as e:
            print(f"\n!!! EROARE la calculul poziției lunii: {e} !!!\n")
            return None, None
    
    def calculate_moon_times(self):
        """Calculate precise moon rise time using Skyfield"""
        try:
            # Determinăm timpul de referință
            if hasattr(self, 'timeshift_datetime'):
                current_time = self.timeshift_datetime
            else:
                current_time = datetime.now(self.current_timezone)
            
            t0 = self.ts.from_datetime(current_time)
            t1 = self.ts.from_datetime(current_time + timedelta(hours=24))
            
            times, events = almanac.find_discrete(t0, t1, 
                almanac.risings_and_settings(self.eph, self.eph['moon'], self.location))
            
            for time, event in zip(times, events):
                if event:  # True = răsărit
                    next_rise = time.astimezone(self.current_timezone)
                    if next_rise < current_time:
                        next_rise = next_rise + timedelta(days=1)
                        
                    time_until_rise = next_rise - current_time
                    hours_until = time_until_rise.total_seconds() / 3600
                    
                    return next_rise, hours_until
            
            return None, None
                    
        except Exception as e:
            print(f"\n!!! EROARE la calculul timpilor lunari: {e} !!!\n")
            return None, None

    def azimuth_to_clock(self, azimuth):
        """Convert azimuth (0-360°) to clock position (1-12)"""
        hour = (azimuth / 30) % 12
        if hour == 0:
            hour = 12
        return int(hour)

    def calculate_moon_distance(self):
        """Calculează distanța până la Lună și oferă informații despre perigeu/apogeu"""
        try:
            time_ref = self.timeshift_ts if hasattr(self, 'timeshift_ts') else self.ts.now()
            earth = self.eph['earth']
            moon = self.eph['moon']
            
            astrometric = earth.at(time_ref).observe(moon)
            distance_km = astrometric.distance().km
            
            PERIGEE_MIN = 356400
            PERIGEE_MAX = 370400
            APOGEE_MIN = 404000
            APOGEE_MAX = 406700
            
            total_range = APOGEE_MAX - PERIGEE_MIN
            current_position = distance_km - PERIGEE_MIN
            # Inversăm ratingul: 10 pentru perigeu, 1 pentru apogeu
            rating = 10 - round((current_position / total_range) * 9)
            
            if PERIGEE_MIN <= distance_km <= PERIGEE_MAX:
                status = f"PERIGEU ({rating}/10)"
                color = "#4CAF50"
            elif APOGEE_MIN <= distance_km <= APOGEE_MAX:
                status = f"APOGEU ({rating}/10)"
                color = "#F44336"
            else:
                status = f"INTERMEDIAR ({rating}/10)"
                color = "#FFC107"
                
            current_position_percent = (current_position / total_range) * 100
            
            return {
                'distance': distance_km,
                'status': status,
                'color': color,
                'percentage': current_position_percent,
                'rating': rating
            }
        except Exception as e:
            print(f"Eroare la calculul distanței lunare: {e}")
            return None

    def calculate_moon_distance_at(self, timestamp):
        try:
            earth = self.eph['earth']
            moon = self.eph['moon']
            
            astrometric = earth.at(timestamp).observe(moon)
            distance_km = astrometric.distance().km
            
            PERIGEE_MIN = 356400
            PERIGEE_MAX = 370400
            APOGEE_MIN = 404000
            APOGEE_MAX = 406700
            
            total_range = APOGEE_MAX - PERIGEE_MIN
            current_position = distance_km - PERIGEE_MIN
            rating = 10 - round((current_position / total_range) * 9)
            
            if PERIGEE_MIN <= distance_km <= PERIGEE_MAX:
                status = f"PERIGEU ({rating}/10)"
                color = "#4CAF50"
            elif APOGEE_MIN <= distance_km <= APOGEE_MAX:
                status = f"APOGEU ({rating}/10)"
                color = "#F44336"
            else:
                status = f"INTERMEDIAR ({rating}/10)"
                color = "#FFC107"
                
            current_position_percent = (current_position / total_range) * 100
            
            return {
                'distance': distance_km,
                'status': status,
                'color': color,
                'percentage': current_position_percent,
                'rating': rating
            }
        except Exception as e:
            print(f"Eroare la calculul distanței lunare: {e}")
            return None
    
    def load_full_moon_ratings(self):
        """Încarcă rating-urile salvate din JSON"""
        try:
            with open('moon_settings.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            if 'full_moon_ratings' in data:
                ratings = []
                for rating in data['full_moon_ratings']:
                    date = datetime.strptime(rating['date'], '%Y-%m-%d %H:%M:%S %z')
                    ratings.append({
                        'date': date,
                        'rating': rating['rating']
                    })
                return ratings
            return []
                
        except Exception as e:
            print(f"Eroare la încărcarea ratings: {e}")
            return []

    def save_full_moon_ratings(self, ratings):
        """Salvează rating-urile în JSON"""
        try:
            with open('moon_settings.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            json_ratings = []
            for rating in ratings:
                json_ratings.append({
                    'date': rating['date'].strftime('%Y-%m-%d %H:%M:%S %z'),
                    'rating': rating['rating']
                })
            
            data['full_moon_ratings'] = json_ratings
            
            with open('moon_settings.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            print(f"Eroare la salvarea ratings: {e}")

    def calculate_full_moon_ratings(self, force_recalc=False):
        """Calculează rating-urile pentru următoarele 12 luni pline"""
        try:
            # Încercăm să încărcăm din JSON dacă nu forțăm recalcularea
            if not force_recalc:
                saved_ratings = self.load_full_moon_ratings()
                if saved_ratings and saved_ratings[0]['date'] > datetime.now(pytz.UTC):
                    print("Folosim datele salvate pentru lunile pline")
                    return saved_ratings
                
            print("Calculăm date noi pentru lunile pline")
            
            start_time = datetime.now(self.current_timezone)
            t0 = self.ts.from_datetime(start_time)
            t1 = self.ts.from_datetime(start_time + timedelta(days=400))
            
            times, phases = almanac.find_discrete(t0, t1, almanac.moon_phases(self.eph))
            
            full_moons = []
            for t, phase in zip(times, phases):
                if phase == 2:  # 2 reprezintă luna plină
                    full_moons.append(t)
                if len(full_moons) >= 12:
                    break
            
            ratings = []
            for moon_time in full_moons:
                distance_info = self.calculate_moon_distance_at(moon_time)
                if distance_info:
                    ratings.append({
                        'date': moon_time.astimezone(self.current_timezone),
                        'rating': distance_info['rating']
                    })
            
            # Salvăm noile calcule
            self.save_full_moon_ratings(ratings)
            
            return ratings
            
        except Exception as e:
            print(f"Eroare la calculul rating-urilor pentru luni pline: {e}")
            return []

    def update_moon_position_display(self):
        """Actualizează afișarea poziției lunii, inclusiv distanța"""
        alt, az = self.calculate_moon_position()
        if alt is not None and az is not None:
            distance_info = self.calculate_moon_distance()
            if distance_info:
                distance_str = f"{distance_info['distance']:,.0f}".replace(",", ".")
                
                progress_bar = f"""
                    <div style='
                        width: 100%;
                        height: 10px;
                        background-color: #404040;
                        border-radius: 5px;
                        margin: 5px 0;
                    '>
                        <div style='
                            width: {distance_info['percentage']}%;
                            height: 100%;
                            background-color: {distance_info['color']};
                            border-radius: 5px;
                            transition: width 0.5s;
                        '></div>
                    </div>
                """
                
                self.elevation_label.setText(f"Elevație: {alt:.2f}° ({'Luna este vizibilă' if alt > 0 else 'Luna nu este vizibilă'})")
                
                # Status și distanță pe același rând
                status_parts = distance_info['status'].split()
                rating_part = status_parts[-1]  # Luăm partea cu (X/10)
                status_name = status_parts[0]   # Luăm numele statusului (APOGEU/PERIGEU/INTERMEDIAR)
                self.distance_label.setText(f"{status_name} {rating_part} • {distance_str} km")
                self.distance_label.setStyleSheet(f"color: {distance_info['color']};")
                self.distance_progress_label.setText(progress_bar)

    def print_moon_status(self):
        """Status lunar"""
        if not hasattr(self, 'last_status_time'):
            self.last_status_time = 0
        
        # Verificăm dacă suntem în mod timeshift
        is_timeshift = hasattr(self, 'timeshift_datetime')
        current_time = unix_time.time()
        
        # Afișăm doar dacă: 
        # - suntem în timeshift SAU
        # - au trecut 5 minute de la ultima afișare
        if not (is_timeshift or current_time - self.last_status_time >= 300):  # 5 minute
            return
            
        self.last_status_time = current_time
        
        print("\n" + "=" * 50)
        print("STATUS LUNĂ - " + (
            f"Timeshift {self.timeshift_datetime.strftime('%Y-%m-%d %H:%M')}" 
            if is_timeshift 
            else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        print("=" * 50)
        
        alt, az = self.calculate_moon_position()
        if alt is not None and az is not None:
            print(f"\n1. POZIȚIE")
            print(f"   Elevație: {alt:.2f}°")
            print(f"   Azimut: {az:.2f}°")
            print(f"   Vizibilitate: {'VIZIBILĂ' if alt > 0 else 'SUB ORIZONT'}")
        
        next_rise, hours_until = self.calculate_moon_times()
        if next_rise:
            t0 = self.ts.from_datetime(next_rise)
            earth = self.eph['earth']
            moon = self.eph['moon']
            astrometric = (earth + self.location).at(t0).observe(moon)
            _, rise_az, _ = astrometric.apparent().altaz()
            
            print(f"\n2. RĂSĂRIT")
            print(f"   Următorul răsărit: {next_rise.strftime('%H:%M')}")
            if hours_until > 0:
                hours = int(hours_until)
                minutes = int((hours_until % 1) * 60)
                print(f"   Timp până la răsărit: {hours}h {minutes}m")
            print(f"   Azimut la răsărit: {rise_az.degrees:.2f}°")
        
        try:
            timestamp = int(unix_time.time())
            response = requests.get(f'https://api.farmsense.net/v1/moonphases/?d={timestamp}')
            data = response.json()[0]
            illumination = float(data['Illumination']) * 100
            varsta_luna = float(data['Age'])
            is_waning = varsta_luna > 14.765
            
            print(f"\n3. FAZA LUNII")
            print(f"   Iluminare: {illumination:.1f}%")
            print(f"   Tendință: {'DESCREȘTERE' if is_waning else 'CREȘTERE'}")
            print(f"   Vârsta: {varsta_luna:.1f} zile")
            
            image_index = round(varsta_luna)
            image_name = f'luna_{image_index}.png'
            print(f"   Imagine: {image_name}")
        except Exception as e:
            print(f"   Eroare la obținerea fazei lunii: {e}")
        
        print("\n" + "=" * 50 + "\n")
    
    def update_all(self):
        """Update timer handler"""
        # Determinăm timpul de referință
        if hasattr(self, 'timeshift_datetime'):
            reference_time = self.timeshift_datetime
            reference_ts = self.timeshift_ts
        else:
            reference_time = datetime.now(self.current_timezone)
            reference_ts = self.ts.now()
        
        timezone_name = self.current_timezone.zone
        self.current_time_label.setText(
            f"Ora locală: {reference_time.strftime('%H:%M:%S')} ({timezone_name})")
        
        alt, az = self.calculate_moon_position()
        self.update_moon_position_display()
        self.update_moon_data()
        if alt is not None and az is not None:
            try:
                # Folosim reference_time în loc de local_time
                future_time = self.ts.from_datetime(reference_time + timedelta(minutes=5))
                earth = self.eph['earth']
                moon = self.eph['moon']
                future_astrometric = (earth + self.location).at(future_time).observe(moon)
                future_alt, _, _ = future_astrometric.apparent().altaz()
                
                elevation_trend = "în urcare" if future_alt.degrees > alt else "în scădere"
            except Exception as e:
                print(f"Eroare la calculul trendului elevației: {e}")
                elevation_trend = "trend nedeterminat"
                
            visibility = "Luna este vizibilă" if alt > 0 else "Luna nu este vizibilă"
            
            # Calculate next rise and set times
            try:
                # Folosim reference_time în loc de local_time
                t0 = self.ts.from_datetime(reference_time)
                t1 = self.ts.from_datetime(reference_time + timedelta(hours=48))
                
                times, events = almanac.find_discrete(t0, t1, 
                    almanac.risings_and_settings(self.eph, self.eph['moon'], self.location))
                
                next_rise_time = None
                next_set_time = None
                
                for time, event in zip(times, events):
                    event_time = time.astimezone(self.current_timezone)
                    
                    if event and next_rise_time is None:  # True = rising
                        next_rise_time = event_time
                    elif not event and next_set_time is None:  # False = setting
                        next_set_time = event_time
                        
                    if next_rise_time and next_set_time:
                        break
                
                def format_time(dt):
                    # Folosim reference_time în loc de local_time
                    if dt.date() == reference_time.date():
                        return dt.strftime('%H:%M')
                    else:
                        return dt.strftime('%H:%M (%d/%m/%Y)')
                
                rise_text = f"Următorul răsărit: {format_time(next_rise_time)}" if next_rise_time else "Răsărit necunoscut"
                set_text = f"Următorul apus: {format_time(next_set_time)}" if next_set_time else "Apus necunoscut"
                
            except Exception as e:
                print(f"Eroare la calculul timpilor răsărit/apus: {e}")
                rise_text = "Răsărit necunoscut"
                set_text = "Apus necunoscut"

            self.elevation_label.setText(f"Elevație: {alt:.2f}° ({visibility})")
            self.azimuth_label.setText(
                f"Elevația este {elevation_trend}\n"
                f"{set_text}\n"
                f"{rise_text}"
            )

            # Update compass widget
            next_rise, hours_until = self.calculate_moon_times()
            if next_rise:
                t0 = self.ts.from_datetime(next_rise)
                astrometric = (earth + self.location).at(t0).observe(moon)
                _, rise_az, _ = astrometric.apparent().altaz()
                rise_azimuth = rise_az.degrees
            else:
                rise_azimuth = 0

            distance_info = self.calculate_moon_distance()
            self.compass_widget.update_position(
                current_azimuth=az,
                rise_azimuth=rise_azimuth,
                is_visible=alt > 0,
                distance_color=distance_info['color'] if distance_info else "#FFC107"
            )
            
            clock_position = self.azimuth_to_clock(az)
            rise_clock = self.azimuth_to_clock(rise_azimuth) if next_rise else 0
            
            self.compass_info_label.setText(
                f"Azimut: {az:.2f}°\n"
                f"Răsare la azimut: {rise_azimuth:.2f}°"
            )

            if next_rise:
                if hours_until > 0:
                    hours = int(hours_until)
                    minutes = int((hours_until % 1) * 60)
                    self.moonrise_time_label.setText(
                        f"Următorul răsărit al Lunii: {next_rise.strftime('%H:%M')} ({timezone_name})\n"
                        f"(în {hours} ore și {minutes} minute)"
                    )
                else:
                    self.moonrise_time_label.setText(
                        f"Următorul răsărit al Lunii: {next_rise.strftime('%H:%M')} ({timezone_name})"
                    )
        
        # Folosim reference_time în loc de local_time
        if reference_time.second == 0:
            self.print_moon_status()
                
    def update_moon_data(self, silent=False):
        """Update moon phase data"""
        try:
            if hasattr(self, 'timeshift_datetime'):
                reference_time = self.timeshift_datetime
            else:
                reference_time = datetime.now(self.current_timezone)
                
            timestamp = int(reference_time.timestamp())
            response = requests.get(f'https://api.farmsense.net/v1/moonphases/?d={timestamp}')
            data = response.json()[0]
            
            illumination = float(data['Illumination']) * 100
            varsta_luna = float(data['Age'])
            is_waning = varsta_luna > 14.765
            
            image_index = round(varsta_luna)
            image_name = f'luna_{image_index}.png'
            image_path = os.path.join('poze_cer', image_name)
            
            alt, az = self.calculate_moon_position()
            next_rise, hours_until = self.calculate_moon_times()
            
            timezone_name = self.current_timezone.zone
            
            if next_rise:
                if hours_until is not None:
                    remaining_str = f" (în {hours_until:.1f} ore)" if hours_until > 0 else ""
                else:
                    remaining_str = ""
                self.moonrise_time_label.setText(
                    f"Următorul răsărit al Lunii: {next_rise.strftime('%H:%M')} ({timezone_name}){remaining_str}")
            
            if os.path.exists(image_path):
                pixmap = QPixmap(image_path)
                self.moon_image.setPixmap(pixmap)
                
                # Formatăm timestamp-ul pentru afișare
                if hasattr(self, 'timeshift_datetime'):
                    time_str = f" (simulat pentru {reference_time.strftime('%d/%m/%Y %H:%M')})"
                else:
                    time_str = f" (la {reference_time.strftime('%H:%M')})"
                
                self.image_name_label.setText(f"Imagine curentă: {image_name}")
                self.phase_label.setText(
                    f"Faza Lunii: {'descreștere' if is_waning else 'creștere'} {round(illumination)}% vizibilă{time_str}")
                self.age_label.setText(
                    f"Vârsta Lunii: {round(varsta_luna)} zile ({timezone_name})")
            else:
                print(f"\n!!! EROARE: Nu s-a găsit imaginea: {image_path} !!!\n")
                self.image_name_label.setText(f"Imagine lipsă: {image_name}")
                
        except Exception as e:
            if not silent:
                self.log_event("DATE LUNĂ", str(e), is_error=True)

def main():
    import win32event
    import win32api
    import winerror
    import sys
    from PyQt5.QtWidgets import QApplication, QMessageBox
    
    mutex_name = 'Global\\MoonHunter_SingleInstance'
    
    try:
        # Încercăm să creăm un mutex cu numele specificat
        handle = win32event.CreateMutex(None, 1, mutex_name)
        if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
            # Mutex-ul există deja, deci o altă instanță rulează
            app = QApplication(sys.argv)
            QMessageBox.warning(None, 'Moon Hunter', 
                              'O altă instanță a aplicației Moon Hunter rulează deja.')
            sys.exit(1)
        
        # Inițializăm aplicația
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        window = MoonPhaseWindow()
        window.show()
        ret = app.exec_()
        
        # La închidere, eliberăm mutex-ul
        win32api.CloseHandle(handle)
        sys.exit(ret)
        
    except Exception as e:
        print(f"Eroare la verificarea single instance: {e}")
        # În caz de eroare, pornim normal
        app = QApplication(sys.argv)
        app.setStyle('Fusion')
        window = MoonPhapeWindow()
        window.show()
        sys.exit(app.exec_())

if __name__ == '__main__':
    main()