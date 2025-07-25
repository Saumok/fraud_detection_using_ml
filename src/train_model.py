import os
os.environ['KMP_DUPLICATE_LIB_OK']='True'  # Prevents OpenMP conflicts
os.environ['OMP_NUM_THREADS']='1'  # Prevents XGBoost threading issues
import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix
import joblib
import logging
from pathlib import Path
from datetime import datetime
import pickle

# Configure paths
BASE_DIR = Path(__file__).parent.parent
PROCESSED_DATA = BASE_DIR / 'data/processed/cleaned_transactions.csv'
MODELS_DIR = BASE_DIR / 'models'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename=BASE_DIR / 'logs/training.log'
)
logger = logging.getLogger(__name__)

def load_data(filepath=PROCESSED_DATA):
    """Load and validate training data with enhanced checks"""
    try:
        if not filepath.exists():
            raise FileNotFoundError(f"Data file {filepath} not found. Ensure:"
                                  f"\n1. preprocess.py ran successfully"
                                  f"\n2. File exists at {filepath}")
        
        df = pd.read_csv(filepath)
        
        # Enhanced validation
        if 'isFraud' not in df.columns:
            raise ValueError("Target column 'isFraud' missing in data")
        if len(df) < 1000:
            logger.warning(f"Low training samples: {len(df)}")
            
        logger.info(f"Successfully loaded {len(df)} records from {filepath}")
        return df
        
    except Exception as e:
        logger.error(f"Data loading failed: {str(e)}")
        raise

def evaluate_model(model, X_test, y_test):
    """Generate comprehensive evaluation metrics"""
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    
    logger.info("\nClassification Report:\n" + classification_report(y_test, y_pred))
    logger.info("\nConfusion Matrix:\n" + str(confusion_matrix(y_test, y_pred)))
    logger.info(f"\nAUC-ROC: {roc_auc_score(y_test, y_proba):.4f}")
    
    return {
        'classification_report': classification_report(y_test, y_pred, output_dict=True),
        'auc_roc': roc_auc_score(y_test, y_proba)
    }

def train_model():
    """Main training pipeline with enhanced logging"""
    try:
        # Ensure directories exist
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        (BASE_DIR / 'logs').mkdir(exist_ok=True)
        
        # Load and validate data
        df = load_data()
        X = df.drop('isFraud', axis=1)
        y = df['isFraud']
        
        # Train-test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, 
            test_size=0.3, 
            random_state=42, 
            stratify=y
        )
        
        # Model configuration with improved defaults
        model = XGBClassifier(
            scale_pos_weight=len(y_train[y_train==0])/max(1, len(y_train[y_train==1])),
            n_estimators=100,  # Reduced for faster training
            max_depth=5,
            learning_rate=0.05,
            tree_method='hist',  # Essential for Streamlit Cloud
            n_jobs=1,  # Critical for stability
            eval_metric='aucpr'  # Better for imbalanced data
        )
        
        # Training with progress logging
        logger.info(f"Training on {len(X_train)} samples...")
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            verbose=10  # More frequent progress updates
        )
        
        # Evaluation
        metrics = evaluate_model(model, X_test, y_test)
        
        # Save artifacts
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = MODELS_DIR / f'fraud_model_{timestamp}.pkl'
        static_path = MODELS_DIR / 'fraud_model_latest.pkl'
        
        joblib.dump(model, model_path)
        joblib.dump(model, static_path)
        
        # Save metrics
        metrics_path = MODELS_DIR / f'model_metrics_{timestamp}.json'
        pd.DataFrame(metrics['classification_report']).to_json(metrics_path)
        
        # Save model.pkl for app compatibility
        with open(MODELS_DIR / 'model.pkl', 'wb') as f:
            pickle.dump(model, f)
        
        # Dummy PCA/KMeans files for app (replace with real ones if available)
        import numpy as np
        from sklearn.decomposition import PCA
        from sklearn.cluster import KMeans
        
        # C features
        pca_c = PCA(n_components=3).fit(X_train.iloc[:, :6])
        km_c = KMeans(n_clusters=2, random_state=42).fit(pca_c.transform(X_train.iloc[:, :6]))
        with open(MODELS_DIR / 'PCA_C_features.pkl', 'wb') as f:
            pickle.dump(pca_c, f)
        with open(MODELS_DIR / 'km_C_features.pkl', 'wb') as f:
            pickle.dump(km_c, f)
        
        # D features
        pca_d = PCA(n_components=3).fit(X_train.iloc[:, :5])
        km_d = KMeans(n_clusters=2, random_state=42).fit(pca_d.transform(X_train.iloc[:, :5]))
        with open(MODELS_DIR / 'PCA_D_features.pkl', 'wb') as f:
            pickle.dump(pca_d, f)
        with open(MODELS_DIR / 'km_D_features.pkl', 'wb') as f:
            pickle.dump(km_d, f)
        
        # V features
        pca_v = PCA(n_components=3).fit(X_train.iloc[:, :11])
        km_v = KMeans(n_clusters=2, random_state=42).fit(pca_v.transform(X_train.iloc[:, :11]))
        with open(MODELS_DIR / 'PCA_V_features.pkl', 'wb') as f:
            pickle.dump(pca_v, f)
        with open(MODELS_DIR / 'km_V_features.pkl', 'wb') as f:
            pickle.dump(km_v, f)
        
        logger.info(f"""
        Training complete!
        - Model saved to: {model_path}
        - Static copy: {static_path}
        - Metrics: {metrics_path}
        - AUC-ROC: {metrics['auc_roc']:.4f}
        """)
        
        return model_path
    
    except Exception as e:
        logger.error(f"Training pipeline failed: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    train_model()