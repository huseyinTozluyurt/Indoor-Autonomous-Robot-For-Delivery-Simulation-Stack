import cv2
import numpy as np
import time
from typing import List, Tuple, Optional, Dict

class SevenSegmentReader:
    def __init__(self):
        # 7-segment gösterge için rakam şablonları (a,b,c,d,e,f,g segmentleri)
        self.digit_patterns = {
            (1,1,1,1,1,1,0): 0,  # 0
            (0,1,1,0,0,0,0): 1,  # 1
            (1,1,0,1,1,0,1): 2,  # 2
            (1,1,1,1,0,0,1): 3,  # 3
            (0,1,1,0,0,1,1): 4,  # 4
            (1,0,1,1,0,1,1): 5,  # 5
            (1,0,1,1,1,1,1): 6,  # 6
            (1,1,1,0,0,0,0): 7,  # 7
            (1,1,1,1,1,1,1): 8,  # 8
            (1,1,1,1,0,1,1): 9,  # 9
        }
        
        # Ayarlanabilir parametreler
        self.min_contour_area = 300
        self.segment_threshold = 0.25
        self.gaussian_kernel = 5
        self.adaptive_block_size = 11
        self.adaptive_c = 2
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Görüntü ön işleme"""
        # Gri tonlama
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
        
        # Kontrast artırma
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
        
        # Gaussian blur ile gürültü azaltma
        blurred = cv2.GaussianBlur(gray, (self.gaussian_kernel, self.gaussian_kernel), 0)
        
        # Adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, self.adaptive_block_size, self.adaptive_c
        )
        
        # Morfolojik işlemler
        kernel = np.ones((3,3), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        return thresh
    
    def find_display_regions(self, thresh_img: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Gösterge bölgelerini bulma"""
        # Konturları bulma
        contours, _ = cv2.findContours(thresh_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        display_regions = []
        
        for contour in contours:
            # Alan kontrolü
            area = cv2.contourArea(contour)
            if area < self.min_contour_area:
                continue
            
            # Bounding rectangle
            x, y, w, h = cv2.boundingRect(contour)
            
            # En-boy oranı kontrolü
            aspect_ratio = float(w) / h
            if 0.2 < aspect_ratio < 3.0:
                display_regions.append((x, y, w, h))
        
        # X koordinatına göre sırala (soldan sağa)
        display_regions.sort(key=lambda x: x[0])
        
        return display_regions
    
    def extract_segments(self, digit_roi: np.ndarray) -> Tuple[int, ...]:
        """Bir rakamın 7 segmentini çıkarma ve analiz etme"""
        if digit_roi.size == 0:
            return (0,0,0,0,0,0,0)
        
        h, w = digit_roi.shape
        
        # Segment bölgelerini tanımlama (göreli koordinatlar)
        segments = {
            'a': (0.15*w, 0.0*h, 0.7*w, 0.25*h),     # Üst yatay
            'b': (0.75*w, 0.0*h, 0.25*w, 0.5*h),     # Üst sağ dikey
            'c': (0.75*w, 0.5*h, 0.25*w, 0.5*h),     # Alt sağ dikey
            'd': (0.15*w, 0.75*h, 0.7*w, 0.25*h),    # Alt yatay
            'e': (0.0*w, 0.5*h, 0.25*w, 0.5*h),      # Alt sol dikey
            'f': (0.0*w, 0.0*h, 0.25*w, 0.5*h),      # Üst sol dikey
            'g': (0.15*w, 0.4*h, 0.7*w, 0.2*h),      # Orta yatay
        }
        
        segment_states = []
        
        for segment_name in ['a', 'b', 'c', 'd', 'e', 'f', 'g']:
            x, y, sw, sh = segments[segment_name]
            x, y, sw, sh = int(x), int(y), int(sw), int(sh)
            
            # Sınır kontrolü
            x = max(0, min(x, w-1))
            y = max(0, min(y, h-1))
            sw = max(1, min(sw, w-x))
            sh = max(1, min(sh, h-y))
            
            # Segment bölgesini çıkar
            segment_roi = digit_roi[y:y+sh, x:x+sw]
            
            if segment_roi.size == 0:
                segment_states.append(0)
                continue
            
            # Segment aktiflik kontrolü
            white_pixels = np.sum(segment_roi > 127)
            total_pixels = segment_roi.size
            
            if total_pixels > 0 and white_pixels / total_pixels > self.segment_threshold:
                segment_states.append(1)
            else:
                segment_states.append(0)
        
        return tuple(segment_states)
    
    def recognize_digit(self, segments: Tuple[int, ...]) -> Optional[int]:
        """Segment durumuna göre rakamı tanıma"""
        return self.digit_patterns.get(segments, None)
    
    def read_floor_number(self, image: np.ndarray) -> Optional[int]:
        """Ana fonksiyon: Asansör kat numarasını okuma"""
        try:
            # Görüntü ön işleme
            thresh = self.preprocess_image(image)
            
            # Gösterge bölgelerini bulma
            display_regions = self.find_display_regions(thresh)
            
            if not display_regions:
                return None
            
            # En büyük bölgeyi asansör göstergesi olarak kabul et
            main_display = max(display_regions, key=lambda x: x[2] * x[3])
            x, y, w, h = main_display
            
            # Gösterge bölgesini çıkar
            display_roi = thresh[y:y+h, x:x+w]
            
            # Rakam bölgelerini bulma
            digit_contours, _ = cv2.findContours(display_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            digits = []
            
            for contour in digit_contours:
                area = cv2.contourArea(contour)
                if area < 50:
                    continue
                
                dx, dy, dw, dh = cv2.boundingRect(contour)
                
                # En-boy oranı kontrolü
                if dh > 0 and 0.3 < dw/dh < 2.0:
                    digit_roi = display_roi[dy:dy+dh, dx:dx+dw]
                    
                    # Segmentleri çıkar
                    segments = self.extract_segments(digit_roi)
                    
                    # Rakamı tanı
                    digit = self.recognize_digit(segments)
                    
                    if digit is not None:
                        digits.append((dx, digit))
            
            if not digits:
                return None
            
            # Rakamları soldan sağa sırala
            digits.sort(key=lambda x: x[0])
            
            # Kat numarasını oluştur
            floor_number = 0
            for _, digit in digits:
                floor_number = floor_number * 10 + digit
            
            return floor_number
            
        except Exception as e:
            print(f"Hata: {e}")
            return None

class FloorTracker:
    def __init__(self):
        self.reader = SevenSegmentReader()
        self.current_floor = None
        self.previous_floor = None
        self.detection_count = 0
        self.required_detections = 3  # Kararlı okuma için gerekli tespit sayısı
        self.last_detection_time = time.time()
        self.floor_history = []
        self.confidence_counter = {}
    
    def update_floor(self, image):
        """Kat bilgisini güncelle"""
        detected_floor = self.reader.read_floor_number(image)
        
        if detected_floor is not None:
            # Güvenlik sayacı
            self.confidence_counter[detected_floor] = self.confidence_counter.get(detected_floor, 0) + 1
            
            # En çok tespit edilen kat
            most_detected = max(self.confidence_counter.items(), key=lambda x: x[1])
            
            if most_detected[1] >= self.required_detections:
                if most_detected[0] != self.current_floor:
                    self.previous_floor = self.current_floor
                    self.current_floor = most_detected[0]
                    
                    # Geçmişe ekle
                    self.floor_history.append({
                        'floor': self.current_floor,
                        'timestamp': time.time(),
                        'previous': self.previous_floor
                    })
                    
                    print(f"Kat değişti: {self.previous_floor} -> {self.current_floor}")
                
                # Sayacı temizle
                self.confidence_counter.clear()
            
            self.last_detection_time = time.time()
        
        # Eski kayıtları temizle
        if len(self.confidence_counter) > 5:
            self.confidence_counter.clear()
        
        return detected_floor
    
    def get_current_floor(self):
        return self.current_floor
    
    def is_stable(self):
        """Son 2 saniyede kararlı okuma var mı?"""
        return time.time() - self.last_detection_time < 2.0

def main():
    """Ana çalıştırma fonksiyonu"""
    print("Asansör Kat Okuyucu Başlatılıyor...")
    print("Çıkmak için 'q' tuşuna basın")
    print("Ayarları değiştirmek için:")
    print("  's' - Segment threshold azalt")
    print("  'S' - Segment threshold artır")
    print("  'a' - Alan threshold azalt")
    print("  'A' - Alan threshold artır")
    print("-" * 50)
    
    # Floor tracker'ı başlat
    tracker = FloorTracker()
    
    # Kamera bağlantısı
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Hata: Kamera açılamadı!")
        # Alternatif kameralar dene
        for i in range(1, 5):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                print(f"Kamera {i} kullanılıyor")
                break
        
        if not cap.isOpened():
            print("Hiçbir kamera bulunamadı!")
            return
    
    # Kamera ayarları
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    # FPS hesaplama için
    fps_counter = 0
    fps_start_time = time.time()
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("Kamera görüntüsü alınamadı!")
                break
            
            # FPS hesaplama
            fps_counter += 1
            current_time = time.time()
            
            # Kat tespiti
            detected_floor = tracker.update_floor(frame)
            current_floor = tracker.get_current_floor()
            
            # Görüntü üzerine bilgi yazma
            info_y = 30
            
            # Mevcut kat
            if current_floor is not None:
                cv2.putText(frame, f"Mevcut Kat: {current_floor}", (10, info_y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                info_y += 40
            
            # Anlık tespit
            if detected_floor is not None:
                cv2.putText(frame, f"Tespit: {detected_floor}", (10, info_y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                info_y += 30
            
            # Kararlılık durumu
            stability_text = "Kararlı" if tracker.is_stable() else "Kararsız"
            color = (0, 255, 0) if tracker.is_stable() else (0, 0, 255)
            cv2.putText(frame, f"Durum: {stability_text}", (10, info_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            info_y += 30
            
            # FPS gösterimi
            if current_time - fps_start_time >= 1.0:
                fps = fps_counter / (current_time - fps_start_time)
                fps_counter = 0
                fps_start_time = current_time
            else:
                fps = 0
            
            if fps > 0:
                cv2.putText(frame, f"FPS: {fps:.1f}", (10, info_y), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Ayarları göster
            settings_text = f"Seg.Thr: {tracker.reader.segment_threshold:.2f} | Area: {tracker.reader.min_contour_area}"
            cv2.putText(frame, settings_text, (10, frame.shape[0] - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            
            # Görüntüyü göster
            cv2.imshow('Asansor Kat Okuyucu', frame)
            
            # Tuş kontrolü
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord('s'):
                tracker.reader.segment_threshold = max(0.1, tracker.reader.segment_threshold - 0.05)
                print(f"Segment threshold: {tracker.reader.segment_threshold:.2f}")
            elif key == ord('S'):
                tracker.reader.segment_threshold = min(0.8, tracker.reader.segment_threshold + 0.05)
                print(f"Segment threshold: {tracker.reader.segment_threshold:.2f}")
            elif key == ord('a'):
                tracker.reader.min_contour_area = max(100, tracker.reader.min_contour_area - 50)
                print(f"Min contour area: {tracker.reader.min_contour_area}")
            elif key == ord('A'):
                tracker.reader.min_contour_area += 50
                print(f"Min contour area: {tracker.reader.min_contour_area}")
            elif key == ord('r'):
                # Ayarları sıfırla
                tracker.reader.segment_threshold = 0.25
                tracker.reader.min_contour_area = 300
                print("Ayarlar sıfırlandı")
    
    except KeyboardInterrupt:
        print("\nProgram kullanıcı tarafından durduruldu")
    
    except Exception as e:
        print(f"Beklenmeyen hata: {e}")
    
    finally:
        # Kaynakları serbest bırak
        cap.release()
        cv2.destroyAllWindows()
        
        # İstatistikleri göster
        print("\n" + "="*50)
        print("ÖZET:")
        print(f"Son tespit edilen kat: {tracker.get_current_floor()}")
        print(f"Toplam kat değişimi: {len(tracker.floor_history)}")
        
        if tracker.floor_history:
            print("\nKat Geçmişi:")
            for record in tracker.floor_history[-5:]:  # Son 5 kayıt
                timestamp = time.strftime("%H:%M:%S", time.localtime(record['timestamp']))
                print(f"  {timestamp}: {record['previous']} -> {record['floor']}")
        
        print("Program sonlandırıldı.")

if __name__ == "__main__":
    main()