"""
Scheduler for managing scheduled message campaigns.
"""

from typing import Optional, Callable, List
from datetime import datetime
import schedule
import threading
import time

from ..models import Campaign
from ..utils.logger import Logger


class CampaignScheduler:
    """Manages scheduled message campaigns."""
    
    def __init__(self):
        """Initialize scheduler."""
        self.scheduled_jobs: List[schedule.Job] = []
        self.scheduler_thread: Optional[threading.Thread] = None
        self.is_running = False
    
    def schedule_campaign(
        self,
        campaign: Campaign,
        run_callback: Callable,
        scheduled_time: datetime
    ) -> bool:
        """
        Schedule a campaign to run at specific time.
        
        Args:
            campaign: Campaign to schedule
            run_callback: Callback function to execute campaign
            scheduled_time: When to run the campaign
            
        Returns:
            True if scheduled successfully, False otherwise
        """
        try:
            hour = scheduled_time.hour
            minute = scheduled_time.minute
            
            # Create scheduled job
            job = schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(
                self._execute_campaign_wrapper,
                campaign=campaign,
                callback=run_callback
            )
            
            self.scheduled_jobs.append(job)
            
            Logger.info(f"Campaign scheduled: {campaign.name} at {hour:02d}:{minute:02d}")
            
            return True
        
        except Exception as e:
            Logger.error(f"Error scheduling campaign: {e}")
            return False
    
    def schedule_recurring(
        self,
        campaign: Campaign,
        run_callback: Callable,
        frequency: str,  # "daily", "weekly", "monthly"
        time_of_day: datetime
    ) -> bool:
        """
        Schedule recurring campaign.
        
        Args:
            campaign: Campaign to schedule
            run_callback: Callback function
            frequency: Recurrence pattern
            time_of_day: Time to run
            
        Returns:
            True if scheduled successfully, False otherwise
        """
        try:
            hour = time_of_day.hour
            minute = time_of_day.minute
            
            if frequency == "daily":
                job = schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(
                    self._execute_campaign_wrapper,
                    campaign=campaign,
                    callback=run_callback
                )
            elif frequency == "weekly":
                # Run on same day each week
                day_name = time_of_day.strftime("%A").lower()
                job = schedule.every().week.at(f"{hour:02d}:{minute:02d}").do(
                    self._execute_campaign_wrapper,
                    campaign=campaign,
                    callback=run_callback
                )
            elif frequency == "monthly":
                # Run on same date each month
                day = time_of_day.day
                job = schedule.every().month.do(
                    self._execute_campaign_wrapper,
                    campaign=campaign,
                    callback=run_callback
                )
            else:
                Logger.error(f"Unknown frequency: {frequency}")
                return False
            
            self.scheduled_jobs.append(job)
            
            Logger.info(f"Recurring campaign scheduled: {campaign.name} ({frequency})")
            
            return True
        
        except Exception as e:
            Logger.error(f"Error scheduling recurring campaign: {e}")
            return False
    
    def start_scheduler(self) -> None:
        """Start the scheduler thread."""
        if self.is_running:
            Logger.warning("Scheduler already running")
            return
        
        self.is_running = True
        self.scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.scheduler_thread.start()
        
        Logger.info("Scheduler started")
    
    def stop_scheduler(self) -> None:
        """Stop the scheduler."""
        self.is_running = False
        Logger.info("Scheduler stopped")
    
    def _run_scheduler(self) -> None:
        """Run the scheduler loop."""
        while self.is_running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def _execute_campaign_wrapper(
        self,
        campaign: Campaign,
        callback: Callable
    ) -> None:
        """
        Wrapper for executing campaign.
        
        Args:
            campaign: Campaign to execute
            callback: Callback to invoke
        """
        try:
            Logger.info(f"Executing scheduled campaign: {campaign.name}")
            callback(campaign)
        except Exception as e:
            Logger.error(f"Error executing scheduled campaign: {e}")
    
    def cancel_campaign(self, job_id: int) -> bool:
        """
        Cancel a scheduled campaign.
        
        Args:
            job_id: Job ID to cancel
            
        Returns:
            True if cancelled successfully, False otherwise
        """
        try:
            if job_id < len(self.scheduled_jobs):
                job = self.scheduled_jobs.pop(job_id)
                schedule.cancel_job(job)
                Logger.info("Scheduled campaign cancelled")
                return True
            return False
        except Exception as e:
            Logger.error(f"Error cancelling campaign: {e}")
            return False
    
    def get_scheduled_campaigns(self) -> List[dict]:
        """
        Get list of all scheduled campaigns.
        
        Returns:
            List of scheduled campaign info
        """
        campaigns = []
        
        for i, job in enumerate(self.scheduled_jobs):
            campaigns.append({
                'id': i,
                'next_run': job.next_run.isoformat() if job.next_run else None,
                'job': str(job)
            })
        
        return campaigns
