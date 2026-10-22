# NavTatva - Maritime Oil Spill Detection & Attribution System

**Smart India Hackathon 2026 | SIH26143**  
**Organization:** National Technical Research Organisation (NTRO)  
**Category:** Software | **Theme:** Space Technology / Disaster Management

---

## 🎯 Project Overview

**NavTatva** (formerly TideTrace) is an advanced maritime surveillance system that leverages satellite imagery and AIS (Automatic Identification System) data to detect oil spills at sea and identify the vessels responsible for pollution. The system operates completely offline on a single laptop, making it ideal for deployment in remote maritime facilities and during disaster response scenarios.

### The Problem We're Solving

Marine oil spills cause devastating environmental damage and often go unattributed. The challenge is to:
- Detect oil slicks from satellite imagery (SAR and optical)
- Trace the spill back to its origin point and time
- Identify the polluting vessel from AIS traffic data
- Provide actionable evidence for maritime authorities

### Our Solution

NavTatva provides a complete end-to-end pipeline that:
1. **Detects** oil slicks in Sentinel-1 SAR imagery using deep learning
2. **Characterizes** the spill geometry (area, length, orientation, etc.)
3. **Hindcasts** the drift physics backwards through real oceanographic data to find the release point
4. **Forecasts** where the slick will drift next
5. **Attributes** the spill to specific vessels using historical AIS data
6. **Ranks** suspect vessels with explainable scoring and evidence trails

**Key Achievement:** Complete offline operation - no internet required at runtime, runs on standard laptop hardware (CPU only or with RTX 4060 8GB GPU).

---

## 🚀 Key Features & Innovations

### 1. **Fully Offline Architecture**
- ✅ No Docker, no cloud services, no runtime API keys
- ✅ All data cached during preparation phase
- ✅ Network can be unplugged during operation
- ✅ Verified by automated tests that block all network access

### 2. **AI-Powered Oil Detection**
- **UNet++** segmentation model (IoU: 0.889 on validation set)
- Trained on 1,164 SAR tiles from Zenodo dataset
- Automatic look-alike rejection (algae, ships, weather patterns)
- Falls back to threshold-based detection if GPU unavailable
- Handles clean scenes correctly (doesn't force false positives)

### 3. **Physics-Based Drift Modeling**
- **Real oceanographic data**: ERA5 winds + CMEMS ocean currents
- **RK2 Lagrangian ensemble** integration (50 particles)
- Hindcast to origin zone (6-48 hours back)
- Forecast dispersion cone (36 hours forward)
- Coastal impact detection

### 4. **Intelligent Vessel Attribution**
- **Multi-factor scoring system:**
  - Proximity to origin point (30% weight)
  - Temporal correlation (20% weight)
  - Vessel behavior anomalies (25% weight)
  - Vessel type priors (15% weight)
  - Trajectory alignment (10% weight)
- **Evidence-based ranking** with confidence scores
- **AIS gap detection** for suspicious non-reporting periods
- Dead reckoning for track reconstruction

### 5. **Professional Interface**
- Interactive web console with Leaflet mapping
- Real-time progress tracking during analysis
- Time-slider for AIS track replay
- Expandable evidence cards per suspect
- Exportable PDF attribution reports
- Light/dark themes with WCAG compliance

### 6. **Production-Ready Quality**
- 126 automated tests (100% passing)
- Reproducible results (deterministic seeding)
- Comprehensive error handling
- Optional dependencies (works without GPU/PyTorch)
- Complete audit trail in job documents

---

## 🎨 Why NavTatva is Different

| Aspect | Traditional Approaches | NavTatva |
|--------|----------------------|----------|
| **Deployment** | Requires cloud services, accounts, APIs | Single laptop, fully offline |
| **Detection** | Rule-based or requires manual interpretation | AI-powered with 88.9% IoU accuracy |
| **Attribution** | Manual correlation of AIS data | Automated multi-factor scoring with evidence |
| **Transparency** | "Black box" results | Explainable scores with reason codes |
| **Clean Scenes** | Often produces false positives | Correctly reports no slick detected |
| **Real-time Data** | Requires live API access | Works with cached historical data |
| **Setup Time** | Hours/days with complex dependencies | Minutes with single requirements file |
| **Hardware** | Needs GPU or cloud compute | Runs on CPU (GPU optional for speed) |

### Technical Innovations

1. **Offline-First Design Pattern**: Network access isolated to preparation scripts, runtime completely air-gapped
2. **Graceful Degradation**: Every optional library has a working fallback implementation
3. **Evidence Transparency**: All calculations exposed via API, weights configurable
4. **Confidence Scoring**: Separates observed data from dead-reckoned assumptions
5. **Absolute Scoring**: Rankings are absolute percentages, not relative to batch
6. **Streaming Architecture**: Processes multi-gigabyte datasets without expanding to disk

---

## 🛠️ Technology Stack

### Core Technologies

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Runtime** | Python 3.11+ | Modern typing, performance |
| **Web Framework** | FastAPI + Uvicorn | Async API, auto-documentation |
| **Deep Learning** | PyTorch + segmentation-models-pytorch | UNet++ oil detection |
| **Geospatial** | Rasterio + PyProj | SAR processing, projections |
| **Numerics** | NumPy + SciPy | Physics simulation, morphology |
| **Database** | SQLite | AIS vessel tracking |
| **Frontend** | Vanilla HTML/CSS/JS + Leaflet | Zero build tools, no frameworks |
| **Validation** | Pydantic v2 | Request/response schemas |
| **Reporting** | ReportLab | PDF generation |

### Why These Choices?

- **FastAPI**: Automatic OpenAPI docs, async support, minimal overhead
- **PyTorch**: Industry standard for segmentation, easy deployment
- **Vanilla JS**: No build tooling, works immediately, no framework lock-in
- **SQLite**: Zero-config database, perfect for AIS queries
- **Optional Dependencies**: Rasterio, PyProj, SciPy all have pure Python fallbacks

### Architecture Highlights

```
┌─────────────────────────────────────────────────────────────┐
│                    OFFLINE BOUNDARY                          │
├─────────────────┬─────────────────┬────────────────────────┤
│  Preparation    │   Data Layer    │    Runtime             │
│  (scripts/)     │   (data/)       │    (app/)              │
│  - Online OK    │   - Files only  │    - No network        │
│  - Runs once    │   - Cache       │    - Reads files       │
│  - Downloads    │   - Interface   │    - Serves console    │
└─────────────────┴─────────────────┴────────────────────────┘
```

**Enforced by Tests:**
- `test_pipeline_offline.py`: Blocks all sockets, runs full pipeline
- `test_offline_boundary.py`: AST parsing prevents network imports

---

## 📊 System Capabilities

### Detection Performance

| Metric | Score |
|--------|-------|
| **IoU (Oil)** | 0.889 |
| **IoU (Sea)** | 0.982 |
| **Mean IoU** | 0.936 |
| **Pixel Accuracy** | 0.984 |
| **False Positive Rate** | 0.011 |

Trained for 40 epochs, best checkpoint at epoch 33.

### Processing Speed

| Operation | CPU Only | With GPU |
|-----------|----------|----------|
| **Full Pipeline** | 30-45s | 10-15s |
| **Detection Only** | 8-12s | 2-4s |
| **Drift Simulation** | 3-5s | 3-5s |
| **AIS Attribution** | 1-3s | 1-3s |

*Tested on laptop with Intel i7 and optional RTX 4060*

### Data Coverage

- **SAR Imagery**: Sentinel-1 IW GRD RTC
- **Optical**: Sentinel-2 L2A (corroboration)
- **Wind Data**: ERA5 10m winds (global)
- **Ocean Currents**: CMEMS (covered regions) + Open-Meteo Marine
- **AIS**: MarineCadastre (US waters) + synthetic (global)
- **Coastlines**: Natural Earth (public domain)

---

## 🎯 Use Cases

### 1. Maritime Enforcement
- **Scenario**: Coast Guard receives satellite imagery of potential spill
- **Solution**: Upload imagery → Get ranked list of suspects with evidence
- **Output**: Attribution report for legal proceedings

### 2. Environmental Monitoring
- **Scenario**: Monitor chronic seepage sites or offshore platforms
- **Solution**: Regular scene analysis, track changes over time
- **Output**: Trend analysis, compliance verification

### 3. Disaster Response
- **Scenario**: Major spill event, need rapid attribution
- **Solution**: Offline operation in field command centers
- **Output**: Real-time drift forecasts, vessel tracking

### 4. Research & Training
- **Scenario**: Study historical spill cases
- **Solution**: Analyze archived imagery against AIS records
- **Output**: Case studies, validation of methods

### 5. Port Security
- **Scenario**: Monitor approaches to sensitive ports
- **Solution**: Continuous surveillance with automated alerts
- **Output**: Threat detection, suspicious behavior flagging

---

## 🚦 Quick Start Guide

### Prerequisites
- Python 3.11 or higher
- 4GB RAM minimum (8GB recommended)
- 10GB free disk space
- Internet connection (for initial setup only)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/NavTatva.git
cd NavTatva/NavTatva-3

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Initial Setup (One-Time, Requires Internet)

```bash
# Bootstrap demo data
python scripts/bootstrap_demo.py

# This will:
# 1. Download Sentinel-1 SAR scenes
# 2. Cache oceanographic data (ERA5 + CMEMS)
# 3. Generate synthetic AIS for demo scenes
# 4. Download coastline data
# 5. Vendor Leaflet mapping library
```

### Optional: Download Trained Model

```bash
# Pull the trained UNet++ checkpoint from Hugging Face
python scripts/hf_sync.py pull-model

# Without this, system uses dB threshold baseline (still works!)
```

### Run the Application

```bash
# Start the server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Open browser to http://127.0.0.1:8000
```

### First Analysis

1. Select a scene from the dropdown (try "Gulf of Mexico MC20")
2. Click **"Run Analysis"**
3. Watch the progress overlay (30-45 seconds)
4. Explore the results:
   - **Investigate**: Detection + drift visualization
   - **Drift**: Backward tracking and forecast
   - **Vessels**: Ranked suspects with evidence
   - **Method**: Scoring formulas and weights
   - **Data**: Technical details and job export

---

## 📁 Project Structure

```
NavTatva-3/
├── app/                      # Main application (OFFLINE)
│   ├── api/                  # FastAPI route handlers
│   │   ├── pipeline.py       # Main analysis endpoint
│   │   ├── ais.py           # AIS queries
│   │   ├── detect.py        # Detection endpoints
│   │   ├── drift.py         # Drift simulation
│   │   └── report.py        # PDF/HTML reports
│   ├── ml/                   # Machine learning
│   │   ├── infer.py         # Tiled inference
│   │   ├── model.py         # UNet++ architecture
│   │   ├── train.py         # Training loop
│   │   └── fallback.py      # Threshold baseline
│   ├── geo/                  # Geospatial operations
│   │   ├── raster.py        # GeoTIFF handling
│   │   ├── geometry.py      # Polygon operations
│   │   └── crs.py           # Coordinate systems
│   ├── drift/                # Physics simulation
│   │   ├── advection.py     # RK2 integrator
│   │   ├── fields.py        # Ocean/wind data
│   │   └── cone.py          # Ensemble analysis
│   ├── ais/                  # Vessel tracking
│   │   ├── ingest.py        # AIS database
│   │   ├── interpolate.py   # Track reconstruction
│   │   ├── filter.py        # Spatial/temporal funnel
│   │   └── score.py         # Attribution scoring
│   ├── static/               # Web interface
│   │   ├── index.html       # Console shell
│   │   ├── app.js           # Frontend logic
│   │   ├── style.css        # Styling
│   │   └── vendor/          # Leaflet library
│   ├── config.py             # Configuration constants
│   ├── main.py               # FastAPI application
│   └── pipeline.py           # Orchestration
├── scripts/                  # Preparation tools (ONLINE OK)
│   ├── bootstrap_demo.py     # One-command setup
│   ├── fetch_sentinel1_scene.py
│   ├── build_metocean_cache.py
│   ├── fetch_marinecadastre_ais.py
│   ├── hf_sync.py           # Model management
│   └── train_kaggle.ipynb   # Training notebook
├── data/                     # Cached datasets
│   ├── sar/                 # SAR imagery + metadata
│   ├── optical/             # Optical corroboration
│   ├── ais/                 # AIS database
│   ├── metocean/            # Wind/current cubes
│   ├── jobs/                # Analysis results
│   └── land/                # Coastline data
├── tests/                    # Test suite (126 tests)
│   ├── test_pipeline_offline.py
│   ├── test_scoring.py
│   ├── test_advection.py
│   └── ...
├── docs/                     # Documentation
│   ├── ARCHITECTURE.md      # System design
│   ├── COMPLIANCE.md        # Quality gates
│   └── screenshots/         # UI images
├── models/                   # Model checkpoints
│   └── oil_unet_best.pt    # Trained UNet++
├── requirements.txt          # Python dependencies
├── pyproject.toml           # Project metadata
└── README.md                # This file
```

---

## 🔬 How It Works

### The Pipeline (10 Stages)

```
1. DETECT      → Find oil polygons in SAR imagery
2. CHAR        → Calculate geometric properties
3. RENDER      → Generate map overlays
4. METOCEAN    → Load cached wind/current data
5. HINDCAST    → Run physics backward to origin
6. FORECAST    → Project future drift cone
7. COAST       → Check for coastal impact
8. AGE_PROXY   → Estimate slick age from drift time
9. AIS         → Query vessels near origin
10. FILTER     → Spatial/temporal funnel
11. SCORE      → Rank suspects with evidence
```

Each stage is timed and logged. Results saved to `data/jobs/<id>.json`.

### Detection Algorithm

1. **Preprocessing**: Multi-look speckle filter (5×5 boxcar)
2. **Tiling**: Split 2048×2048 chip into 512×512 tiles with overlap
3. **Inference**: UNet++ predicts oil/sea/lookalike per pixel
4. **Stitching**: Cosine-tapered blend in overlap regions
5. **Post-processing**: Connected components, size filtering
6. **Characterization**: Contours in local AEQD projection

**Fallback**: If no GPU/model, uses adaptive threshold (sea median - 3dB)

### Drift Physics

**Velocity Model:**
```
V = U_current + α * U_wind
α = 0.03  (wind factor)
Optional: 15° rightward deflection (northern hemisphere leeway)
```

**Integration:**
- Method: Runge-Kutta 2nd order (RK2)
- Timestep: 1 hour
- Ensemble: 50 particles with velocity perturbations
- Frame: Local azimuthal equidistant (recentered each step)

**Origin Detection:**
- Find first hour where ensemble spread > 8km
- Clipped to 6-48 hour range
- Creates search zone with stated confidence

### Attribution Scoring

**Five Sub-Scores (Weighted):**

1. **Proximity (30%)**: `exp(-distance_km / zone_radius)`
2. **Time (20%)**: `exp(-|Δt| / 1.5 hours)`
3. **Behavior (25%)**: Max of:
   - AIS gap near origin (0.95)
   - Operational speed 8-16kn (0.70)
   - Course change >30° (0.60)
   - Speed swing >5kn (0.50)
4. **Vessel Type (15%)**: Prior probabilities
   - Crude oil tanker: 1.00
   - Chemical tanker: 0.90
   - Fishing: 0.20
   - Unknown: 0.30
5. **Trajectory (10%)**: Course alignment to slick bearing

**Confidence Adjustment:**
```
confidence = 1.0 - 0.65 * (dead_reckoned_fraction)
final_score = raw_score * confidence
```

**Result**: Absolute percentage (not normalized), empty if no strong suspects

---

## 📈 Validation & Testing

### Test Coverage

- **126 tests** covering all major subsystems
- **100% pass rate** in CI/CD
- **17 second** test suite runtime

### Key Test Scenarios

1. **Offline Guarantee**: Full pipeline with network blocked
2. **Physics Validation**: Known trajectories reproduced exactly
3. **Scoring Logic**: Proximity/type/behavior weights verified
4. **Edge Cases**: Clean scenes, empty AIS, missing data
5. **Conformance**: Regression tests for past bugs
6. **Security**: No tokens/credentials in repository

### Real-World Validation

**Demo Scenes:**

| Scene | Location | Date | Status | Validation |
|-------|----------|------|--------|-----------|
| MC20 | Gulf of Mexico | 2023-09-24 | Chronic discharge | Real AIS, correct vessel types |
| Baku | Caspian Sea | 2023-10-14 | Natural seeps | Simulated AIS, origin detected |
| Mumbai | Arabian Sea | 2024-03-13 | Clean water | Correctly reports no slick |
| Santa Barbara | Pacific | 2023-08-29 | Natural seeps | Real AIS, coastal dynamics |

---

## 🎓 API Documentation

### Interactive Docs

Once running, visit:
- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

### Key Endpoints

#### Run Full Analysis
```http
POST /api/run
Content-Type: application/json

{
  "scene_id": "gom_mc20_chronic_slick",
  "hindcast_hours": 48,
  "forecast_hours": 36
}
```

#### Upload Custom Scene
```http
POST /api/detect/upload
Content-Type: multipart/form-data

file: <SAR_GeoTIFF>
```

#### Get Vessel Track
```http
GET /api/ais/track/367123456
```

#### Export Attribution Report
```http
GET /api/report/{job_id}/pdf
```

---

## ⚙️ Configuration

All constants in `app/config.py` can be overridden via environment variables:

```bash
# Drift physics
export TIDETRACE_ALPHA_WIND=0.03
export TIDETRACE_DEFLECTION_DEG=15
export TIDETRACE_ENSEMBLE_N=50

# Attribution weights
export TIDETRACE_W_PROX=0.30
export TIDETRACE_W_TIME=0.20
export TIDETRACE_W_BEH=0.25
export TIDETRACE_W_TYPE=0.15
export TIDETRACE_W_TRAJ=0.10

# Detection
export TIDETRACE_TILE=512
export TIDETRACE_OIL_DB_THRESHOLD=-22.0

# Mode
export TIDETRACE_OFFLINE=1
```

---

## 🌊 Datasets & Licenses

| Data Source | Purpose | License | Attribution |
|-------------|---------|---------|-------------|
| Zenodo SAR Oil Spill Dataset | Training | CC BY 4.0 | Krestenitis et al. |
| Sentinel-1 RTC | SAR imagery | CC BY 4.0 | ESA Copernicus |
| Sentinel-2 L2A | Optical corroboration | CC BY 4.0 | ESA Copernicus |
| ERA5 Reanalysis | Wind fields | CC BY 4.0 | ECMWF |
| CMEMS | Ocean currents | EU Copernicus | Attribution required |
| MarineCadastre AIS | Vessel positions | Public Domain | US Government |
| Natural Earth | Coastlines | Public Domain | - |

**All data sources are cited in outputs and reports.**

---

## 🔒 Limitations & Future Work

### Current Limitations

1. **Model Coverage**: Trained on dual-pol (VV/VH) Sentinel-1 only
2. **Geographic Scope**: Ocean currents unavailable for some basins (e.g., Caspian)
3. **AIS Coverage**: Real data limited to US waters
4. **Look-alike Detection**: Only in dB baseline mode, not UNet++
5. **Weathering**: Age estimate is drift time, not chemical weathering state

### Planned Enhancements

- [ ] Multi-sensor fusion (SAR + optical simultaneous detection)
- [ ] Look-alike classification in neural model
- [ ] Real-time AIS stream integration
- [ ] Multi-day long-term drift forecasting
- [ ] Mobile app for field operations
- [ ] Automated alert generation
- [ ] Integration with EMSA CleanSeaNet
- [ ] Support for additional SAR platforms (RADARSAT, SAOCOM)

---

## 🤝 Contributing & Support

### Team

**Project Lead**: [Your Name]  
**ML Engineer**: [Name]  
**Backend Developer**: [Name]  
**Frontend Developer**: [Name]  
**Domain Expert**: [Name]  

### Contact

- **Email**: [your.email@example.com]
- **GitHub**: [github.com/yourorg/NavTatva]
- **Documentation**: [docs.navtatva.io]

### Acknowledgments

- National Technical Research Organisation (NTRO) for problem statement
- Smart India Hackathon organizing committee
- Sentinel-1 and Copernicus programs for open data
- Kaggle for training compute resources
- Open source community for foundational tools

---

## 📄 License

This project is developed for Smart India Hackathon 2026.

**Code**: MIT License  
**Documentation**: CC BY 4.0  
**Model Weights**: CC BY-NC 4.0 (non-commercial use)

---

## 🏆 Achievements

- ✅ **Complete Offline Operation**: Only SIH project with verified air-gapped capability
- ✅ **Production Quality**: 126 automated tests, full CI/CD pipeline
- ✅ **Real-World Tested**: Validated on 4 diverse maritime environments
- ✅ **Explainable AI**: Every decision traceable with evidence
- ✅ **Deployment Ready**: Single-command installation, no complex setup
- ✅ **Resource Efficient**: Runs on laptop CPU, GPU optional
- ✅ **Open Science**: All methods documented, weights configurable

---

## 📚 References & Resources

### Academic Background

1. Krestenitis et al. (2021) - "Oil Spill Identification from SAR Images"
2. Fingas & Brown (2018) - "A Review of Oil Spill Remote Sensing"
3. De Dominicis et al. (2013) - "MEDSLIK-II Oil Spill Model"

### Technical Documentation

- [Full Architecture Guide](docs/ARCHITECTURE.md)
- [Compliance & Quality](docs/COMPLIANCE.md)
- [API Reference](http://127.0.0.1:8000/docs)
- [Training Notebook](scripts/train_kaggle.ipynb)

### External Resources

- [Sentinel-1 Product Guide](https://sentinels.copernicus.eu/web/sentinel/technical-guides/sentinel-1-sar)
- [MarineCadastre AIS](https://marinecadastre.gov/ais/)
- [CMEMS Documentation](https://marine.copernicus.eu/)
- [ERA5 Dataset](https://www.ecmwf.int/en/forecasts/dataset/ecmwf-reanalysis-v5)

---

## 🎯 SIH Evaluation Criteria Mapping

| Criterion | How NavTatva Addresses It |
|-----------|---------------------------|
| **Innovation** | Offline-first architecture, multi-factor attribution, explainable AI |
| **Technical Complexity** | Deep learning, physics simulation, geospatial processing, multi-source data fusion |
| **Scalability** | Minimal hardware requirements, no cloud dependency, efficient algorithms |
| **Usability** | One-click analysis, intuitive interface, comprehensive documentation |
| **Social Impact** | Protects marine ecosystems, enables enforcement, disaster response ready |
| **Completeness** | All three PS clauses fully implemented and tested |
| **Code Quality** | 126 tests, type hints, documentation, clean architecture |
| **Feasibility** | Proven on real data, deployable today, practical constraints respected |

---

<div align="center">

**Built with ❤️ for Smart India Hackathon 2026**

*Protecting Our Oceans Through Technology*

[Demo Video](#) | [Live Demo](#) | [Documentation](docs/) | [GitHub](#)

</div>
