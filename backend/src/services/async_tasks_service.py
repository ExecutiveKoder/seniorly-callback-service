"""
Async Tasks Service
Handles background tasks that don't need to block the conversation
- Sending emails with research results
- Generating detailed reports
- Syncing analytics data
"""
import logging
import threading
from typing import Dict, List, Callable
from queue import Queue
from datetime import datetime

logger = logging.getLogger(__name__)


class AsyncTasksService:
    """Service to handle background tasks asynchronously"""

    def __init__(self):
        """Initialize async task queue"""
        self.task_queue = Queue()
        self.worker_thread = None
        self.running = False

    def start_worker(self):
        """Start background worker thread"""
        if self.running:
            logger.warning("Worker already running")
            return

        self.running = True
        self.worker_thread = threading.Thread(target=self._process_tasks, daemon=True)
        self.worker_thread.start()
        logger.info("✅ Async task worker started")

    def stop_worker(self):
        """Stop background worker thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("🛑 Async task worker stopped")

    def queue_task(self, task_name: str, task_func: Callable, *args, **kwargs):
        """
        Queue a task to run asynchronously

        Args:
            task_name: Human-readable task name
            task_func: Function to execute
            *args, **kwargs: Arguments for the function
        """
        task = {
            'name': task_name,
            'func': task_func,
            'args': args,
            'kwargs': kwargs,
            'queued_at': datetime.now()
        }

        self.task_queue.put(task)
        logger.info(f"📝 Queued async task: {task_name}")

    def _process_tasks(self):
        """Worker thread that processes tasks from queue"""
        logger.info("🔄 Task processor started")

        while self.running:
            try:
                # Get task from queue (block for 1 second)
                task = self.task_queue.get(timeout=1)

                logger.info(f"⚙️  Processing task: {task['name']}")

                # Execute the task
                try:
                    result = task['func'](*task['args'], **task['kwargs'])

                    queued_time = (datetime.now() - task['queued_at']).total_seconds()
                    logger.info(f"✅ Task completed: {task['name']} (queued for {queued_time:.1f}s)")

                except Exception as task_error:
                    logger.error(f"❌ Task failed: {task['name']} - {task_error}")

                finally:
                    self.task_queue.task_done()

            except:
                # Queue timeout - continue loop
                continue

        logger.info("🔄 Task processor stopped")

    def get_queue_size(self) -> int:
        """Get number of pending tasks"""
        return self.task_queue.qsize()


# Global instance
async_tasks = AsyncTasksService()


# Convenience functions
def queue_email_send(email_service, recipient: str, subject: str, content: str):
    """Queue an email to be sent asynchronously"""
    async_tasks.queue_task(
        task_name=f"Send email to {recipient}",
        task_func=email_service._send_email,
        to_email=recipient,
        subject=subject,
        html_content=content
    )


def queue_research_email(
    email_service,
    research_service,
    recipient_email: str,
    recipient_name: str,
    research_topic: str,
    search_query: str,
    search_type: str = 'educational'
):
    """
    Queue a research + email task

    Args:
        email_service: EmailService instance
        research_service: ResearchService instance
        recipient_email: Senior's email
        recipient_name: Senior's name
        research_topic: Topic description
        search_query: What to search for
        search_type: 'educational', 'doctors', 'services'
    """

    def do_research_and_email():
        """Perform research and send email"""
        try:
            logger.info(f"🔍 Researching: {search_query}")

            # Perform research based on type
            if search_type == 'doctors':
                # Extract location from query or use default
                results = research_service.search_nearby_doctors(
                    condition=research_topic,
                    location='Toronto, ON'  # TODO: Get from senior profile
                )
            elif search_type == 'services':
                results = research_service.search_local_services(
                    service_type=research_topic,
                    location='Toronto, ON'
                )
            else:
                # Educational resources
                results = research_service.search_educational_resources(
                    topic=search_query,
                    senior_friendly=True
                )

            if not results:
                logger.warning(f"No results found for: {search_query}")
                return False

            logger.info(f"📚 Found {len(results)} results")

            # Send email with results
            success = email_service.send_research_results(
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                research_topic=research_topic,
                results=results,
                include_disclaimer=True
            )

            return success

        except Exception as e:
            logger.error(f"Research and email task failed: {e}")
            return False

    async_tasks.queue_task(
        task_name=f"Research '{research_topic}' and email to {recipient_name}",
        task_func=do_research_and_email
    )


# Start worker when module loads
async_tasks.start_worker()
