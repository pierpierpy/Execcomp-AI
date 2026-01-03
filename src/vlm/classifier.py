"""
SCT Classifier - Binary classifier for Summary Compensation Tables.

Uses a fine-tuned Qwen3-VL-4B model with a classification head to determine
if a table image is a Summary Compensation Table.

Usage:
    from src.vlm.classifier import SCTClassifier
    
    classifier = SCTClassifier()
    prob = classifier.classify(image)  # Single image
    probs = classifier.classify_batch(images)  # Batch
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path
from typing import Union, List, Optional
from PIL import Image
from tqdm.auto import tqdm

# Lazy imports for heavy dependencies
_processor = None
_model = None


class VLMClassifier(nn.Module):
    """VLM with classification head."""
    
    def __init__(self, base_model, hidden_size: int = None, num_labels: int = 2):
        super().__init__()
        self.base_model = base_model
        
        # Get hidden size from config
        if hidden_size is None:
            if hasattr(base_model.config, 'text_config'):
                hidden_size = base_model.config.text_config.hidden_size
            else:
                hidden_size = base_model.config.hidden_size
        
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size, 512),
            nn.ReLU(),
            nn.Dropout(0.1),
            nn.Linear(512, num_labels)
        )
        
    def forward(self, input_ids, attention_mask, pixel_values, image_grid_thw):
        outputs = self.base_model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            pixel_values=pixel_values,
            image_grid_thw=image_grid_thw,
            output_hidden_states=True,
            return_dict=True
        )
        hidden_states = outputs.hidden_states[-1]
        pooled = hidden_states.mean(dim=1)
        logits = self.classifier(pooled.float())
        return logits


class SCTClassifier:
    """
    Binary classifier for Summary Compensation Tables.
    
    Args:
        model_path: Path to the saved model directory (with classifier_head.safetensors)
        device: Device to run on ('cuda' or 'cpu')
        threshold: Probability threshold for is_sct classification
    """
    
    DEFAULT_MODEL_PATH = Path(__file__).parent.parent.parent / "hf/models/exp2-weighted-loss-qwen3/full"
    
    def __init__(
        self, 
        model_path: Union[str, Path] = None,
        device: str = "cuda",
        threshold: float = 0.5
    ):
        self.model_path = Path(model_path) if model_path else self.DEFAULT_MODEL_PATH
        self.device = device
        self.threshold = threshold
        self._model = None
        self._processor = None
        
    def _load_model(self):
        """Lazy load model on first use."""
        if self._model is not None:
            return
        
        from transformers import AutoModelForVision2Seq, AutoProcessor
        from safetensors.torch import load_file
        import json
        
        # Load config
        config_path = self.model_path / "classifier_config.json"
        with open(config_path) as f:
            config = json.load(f)
        
        print(f"Loading SCT Classifier from {self.model_path}...")
        
        # Load processor and base model
        self._processor = AutoProcessor.from_pretrained(str(self.model_path))
        base_model = AutoModelForVision2Seq.from_pretrained(
            str(self.model_path),
            torch_dtype=torch.bfloat16,
            device_map=self.device
        )
        
        # Create classifier and load head weights
        self._model = VLMClassifier(
            base_model, 
            hidden_size=config["hidden_size"],
            num_labels=config["num_labels"]
        ).to(self.device)
        
        head_path = self.model_path / "classifier_head.safetensors"
        self._model.classifier.load_state_dict(load_file(head_path))
        self._model.eval()
        
        print(f"✓ SCT Classifier loaded (threshold={self.threshold})")
    
    def _prepare_input(self, image: Image.Image) -> dict:
        """Prepare single image for classification."""
        messages = [[{
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": "Classify this table."}
            ]
        }]]
        
        texts = [self._processor.apply_chat_template(m, tokenize=False, add_generation_prompt=True) for m in messages]
        inputs = self._processor(text=texts, images=[image], padding=True, return_tensors="pt")
        return inputs
    
    def classify(self, image: Union[str, Path, Image.Image]) -> float:
        """
        Classify a single image.
        
        Args:
            image: PIL Image, or path to image file
            
        Returns:
            Probability that the image is a Summary Compensation Table (0-1)
        """
        self._load_model()
        
        # Load image if path
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert("RGB")
        elif not isinstance(image, Image.Image):
            raise ValueError(f"Expected PIL Image or path, got {type(image)}")
        
        inputs = self._prepare_input(image)
        
        with torch.no_grad():
            input_ids = inputs["input_ids"].to(self.device)
            attention_mask = inputs["attention_mask"].to(self.device)
            pixel_values = inputs["pixel_values"].to(self.device, dtype=torch.bfloat16)
            image_grid_thw = inputs["image_grid_thw"].to(self.device)
            
            logits = self._model(input_ids, attention_mask, pixel_values, image_grid_thw)
            probs = F.softmax(logits, dim=-1)
        
        return probs[0, 1].item()  # P(SCT)
    
    def classify_batch(
        self, 
        images: List[Union[str, Path, Image.Image]],
        batch_size: int = 4,
        show_progress: bool = True
    ) -> List[float]:
        """
        Classify multiple images.
        
        Args:
            images: List of PIL Images or paths
            batch_size: Batch size for processing
            show_progress: Show progress bar
            
        Returns:
            List of probabilities (0-1)
        """
        self._load_model()
        
        results = []
        iterator = range(0, len(images), batch_size)
        if show_progress:
            iterator = tqdm(iterator, desc="Classifying", total=(len(images) + batch_size - 1) // batch_size)
        
        for i in iterator:
            batch_images = []
            for img in images[i:i + batch_size]:
                if isinstance(img, (str, Path)):
                    img = Image.open(img).convert("RGB")
                batch_images.append(img)
            
            # Process batch
            messages_batch = []
            for img in batch_images:
                messages_batch.append([{
                    "role": "user",
                    "content": [
                        {"type": "image", "image": img},
                        {"type": "text", "text": "Classify this table."}
                    ]
                }])
            
            texts = [self._processor.apply_chat_template(m, tokenize=False, add_generation_prompt=True) for m in messages_batch]
            inputs = self._processor(text=texts, images=batch_images, padding=True, return_tensors="pt")
            
            with torch.no_grad():
                input_ids = inputs["input_ids"].to(self.device)
                attention_mask = inputs["attention_mask"].to(self.device)
                pixel_values = inputs["pixel_values"].to(self.device, dtype=torch.bfloat16)
                image_grid_thw = inputs["image_grid_thw"].to(self.device)
                
                logits = self._model(input_ids, attention_mask, pixel_values, image_grid_thw)
                probs = F.softmax(logits, dim=-1)
            
            results.extend(probs[:, 1].cpu().tolist())
        
        return results
    
    def is_sct(self, image: Union[str, Path, Image.Image]) -> bool:
        """Check if image is SCT using threshold."""
        return self.classify(image) >= self.threshold
