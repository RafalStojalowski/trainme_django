from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from home.voice_finetune_service import VoiceFinetuneService


class Command(BaseCommand):
    help = (
        "Fine-tunes XTTS's GPT layer on a user's own recordings (real GPU "
        "training). Only ever run manually — see plan/README for why this "
        "isn't triggered automatically at conversation end."
    )

    def add_arguments(self, parser):
        parser.add_argument("username", type=str)
        parser.add_argument(
            "--check", action="store_true",
            help="Only report readiness (collected audio duration), don't train.",
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options["username"])
        except User.DoesNotExist:
            raise CommandError(f"No such user: {options['username']}")

        service = VoiceFinetuneService()
        duration = service.total_duration_seconds(user)
        ready = service.is_ready(user)
        self.stdout.write(f"Zebrano {duration:.1f}s nagrań dla {user.username}.")

        if options["check"]:
            self.stdout.write("Gotowy do treningu." if ready else "Za mało nagrań.")
            return

        if not ready:
            raise CommandError(
                f"Za mało nagrań do treningu (potrzeba >= "
                f"{settings.TTS_FINETUNE_MIN_SECONDS:.0f}s)."
            )

        self.stdout.write("Start fine-tuningu (to może potrwać długo)...")
        checkpoint_dir = service.finetune_user(user)
        self.stdout.write(self.style.SUCCESS(f"Gotowe: {checkpoint_dir}"))
