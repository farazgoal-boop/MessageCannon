"""License manager for MessageCannon."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from .paths import get_license_path as get_app_license_path
from .constants import PAID_PASSKEY, TRIAL_DAYS
from . import license_crypto


class LicenseManager:
    """Manages license verification and trial period."""
    
    LICENSE_FILE = "license.lic"
    
    @staticmethod
    def get_license_path() -> Path:
        """Get license file path."""
        return get_app_license_path()
    
    @staticmethod
    def check_license() -> Dict[str, Any]:
        """
        Check license status.
        
        Returns:
            Dictionary with keys: status, days_remaining, is_trial, is_valid
        """
        license_file = LicenseManager.get_license_path()
        
        # Load or create trial
        if not license_file.exists():
            return LicenseManager._create_trial()
        
        try:
            with open(license_file, 'r') as f:
                license_data = json.load(f)
            
            return LicenseManager._validate_license(license_data)
        except Exception:
            # On error, return trial status
            return LicenseManager._create_trial()
    
    @staticmethod
    def _create_trial() -> Dict[str, Any]:
        """
        Create new trial license.
        
        Returns:
            Trial status dictionary
        """
        trial_start = datetime.now()
        trial_end = trial_start + timedelta(days=TRIAL_DAYS)
        
        license_data = {
            "type": "trial",
            "trial_start": trial_start.isoformat(),
            "trial_end": trial_end.isoformat(),
            "license_key": None,
        }
        
        # Save to file
        license_file = LicenseManager.get_license_path()
        with open(license_file, 'w') as f:
            json.dump(license_data, f)
        
        return {
            "status": "trial",
            "days_remaining": TRIAL_DAYS,
            "is_trial": True,
            "is_valid": True,
        }
    
    @staticmethod
    def _validate_license(license_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate license data.
        
        Args:
            license_data: License dictionary
            
        Returns:
            Validation result dictionary
        """
        license_type = license_data.get("type", "trial")
        
        if license_type == "trial":
            trial_start_str = license_data.get("trial_start")
            if not trial_start_str:
                return LicenseManager._create_trial()

            trial_start = datetime.fromisoformat(trial_start_str)
            # Recompute the effective trial end from the current product policy so
            # older stored trial files cannot keep a longer legacy trial window.
            trial_end = trial_start + timedelta(days=TRIAL_DAYS)
            now = datetime.now()

            days_remaining = (trial_end - now).days
            
            if days_remaining < 0:
                return {
                    "status": "expired",
                    "days_remaining": 0,
                    "is_trial": True,
                    "is_valid": False,
                }
            
            return {
                "status": "trial",
                "days_remaining": max(0, days_remaining),
                "is_trial": True,
                "is_valid": True,
            }
        
        elif license_type == "commercial":
            license_key = license_data.get("license_key")

            if LicenseManager._verify_license_key(license_key):
                return {
                    "status": "licensed",
                    "days_remaining": None,
                    "is_trial": False,
                    "is_valid": True,
                }
            else:
                # A real license file from THIS machine that no longer
                # verifies (a genuinely wrong/forged code, or one issued for
                # a different machine's request code -- e.g. a cloned disk/
                # VM, or a leaked activation code someone tried to reuse on
                # a machine it wasn't signed for) is reported distinctly
                # from "never activated," matching Item 36's own
                # machine-binding guarantee: an activation code only ever
                # verifies against the exact machine fingerprint it was
                # signed for.
                return {
                    "status": "invalid",
                    "days_remaining": 0,
                    "is_trial": False,
                    "is_valid": False,
                }
        
        return {
            "status": "unknown",
            "days_remaining": 0,
            "is_trial": False,
            "is_valid": False,
        }
    
    @staticmethod
    def get_request_code() -> str:
        """Item 36: the human-shareable, machine-bound request code the
        user copies and sends to the seller — the seller signs this exact
        string (via scripts/generate_license.py) into an activation code
        only this machine's fingerprint will ever verify against."""
        return license_crypto.machine_request_code()

    @staticmethod
    def _verify_license_key(license_key: Optional[str]) -> bool:
        """
        Verify a real activation code against THIS machine's own current
        request code, via Ed25519 signature verification (Item 36) —
        replacing the previous single hardcoded PAID_PASSKEY string
        (identical for every buyer, compiled directly into the shipped
        EXE — recoverable via decompilation and reusable to activate any
        install). An activation code only ever verifies for the exact
        machine it was signed for; copying a license.lic file (or an
        activation code) to a different machine produces a different
        request code, which the same signature will not verify against.

        Args:
            license_key: the activation code to verify (format:
                "ACT-XXXXX-XXXXX-...")

        Returns:
            True if valid for this machine, False otherwise
        """
        if not license_key:
            return False

        request_code = license_crypto.machine_request_code()
        if license_crypto.verify_activation_code(request_code, license_key):
            return True

        # Legacy fallback, kept ONLY for backward compatibility with real
        # customers who already activated under the old shared-passkey
        # scheme before this fix — never shown/offered as a path for a NEW
        # activation (the UI only ever displays/accepts the new
        # ACT-...-signed format), so this can't be used to newly unlock an
        # install; it only keeps an already-activated real install working
        # after this upgrade instead of silently locking a paying customer
        # out. Real fix for the underlying problem (one shared secret,
        # identical for every buyer, compiled into the shipped EXE) is the
        # crypto path above.
        return license_key.strip() == PAID_PASSKEY

    @staticmethod
    def activate_license(license_key: str) -> Dict[str, Any]:
        """
        Activate a commercial license.

        Args:
            license_key: License key to activate

        Returns:
            Activation result dictionary
        """
        if not LicenseManager._verify_license_key(license_key):
            return {"success": False, "message": "Invalid activation code for this computer."}

        license_data = {
            "type": "commercial",
            "license_key": license_key.strip().upper(),
            "activated_at": datetime.now().isoformat(),
            "machine_fingerprint": license_crypto.machine_fingerprint(),
        }

        license_file = LicenseManager.get_license_path()
        try:
            with open(license_file, 'w') as f:
                json.dump(license_data, f)

            return {"success": True, "message": "License activated successfully"}
        except Exception as e:
            return {"success": False, "message": f"Failed to activate license: {str(e)}"}

    @staticmethod
    def deactivate_license() -> Dict[str, Any]:
        """Deactivate a commercial license without resetting the free trial."""
        license_file = LicenseManager.get_license_path()

        if not license_file.exists():
            return {"success": False, "message": "No active license found"}

        try:
            with open(license_file, 'r') as f:
                license_data = json.load(f)

            if license_data.get("type") != "commercial":
                return {"success": False, "message": "No commercial license is active"}

            expired_start = datetime.now() - timedelta(days=TRIAL_DAYS + 1)
            expired_end = expired_start + timedelta(days=TRIAL_DAYS)
            replacement_data = {
                "type": "trial",
                "trial_start": expired_start.isoformat(),
                "trial_end": expired_end.isoformat(),
                "license_key": None,
                "deactivated_at": datetime.now().isoformat(),
            }

            with open(license_file, 'w') as f:
                json.dump(replacement_data, f)

            return {"success": True, "message": "License deactivated successfully"}
        except Exception as e:
            return {"success": False, "message": f"Failed to deactivate license: {str(e)}"}
