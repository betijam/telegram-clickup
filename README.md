# Telegram -> ClickUp bots (Vercel versija)

Sis ir vienkars bots, kas jebkuru Telegram tekstu vai balss zinu var parverst par ClickUp uzdevumu viena noteikta liste.

## Ka tas strada

- Telegram sutis webhook pieprasijumu uz Vercel.
- `webhook.py` apstradas tekstu vai balss zinu.
- Bots izveidos uzdevumu tiesi tajaa ClickUp liste, ko nosaka `CLICKUP_LIST_ID`.

## Vides mainigie

Vercel projektam pievieno:

| Nosaukums | Obligats | Apraksts |
|---|---|---|
| `TELEGRAM_TOKEN` | ja | Telegram bota token |
| `CLICKUP_API_KEY` | ja | ClickUp API piekluve |
| `CLICKUP_LIST_ID` | ja | Vienas ClickUp listes ID |
| `CLICKUP_ASSIGNEE_ID` | ne | ClickUp user ID, kam visus taskus assignot |
| `TELEGRAM_BOT_USERNAME` | ne | Bota username grupu mentioniem, ja negribi paļauties uz auto-detekciju |
| `WEBHOOK_SECRET` | ne | Papildu Telegram webhook aizsardziba |
| `OPENAI_API_KEY` | ne | Vajadzigs, ja gribi apstradat balss zinas |
| `OPENAI_TRANSCRIBE_MODEL` | ne | Pec noklusejuma `gpt-4o-mini-transcribe` |
| `OPENAI_TASK_REWRITE` | ne | `auto` pec noklusejuma, vai `off`, ja negribi AI sakartotu title/description |

Pec izmainam Vercel vajag `Redeploy`.

## Webhook uzstadisana

```bash
pip install requests
python setup_webhook.py
```

Ievadi savu Telegram token un Vercel URL, piemeram `https://tavs-projekts.vercel.app`.

## Ka lietot

### Dabiska valoda tekstam

Vari vienkarsi rakstit:

```text
Salabot login formu. Klienti netiek ieksa. Tas ir steidzami.
```

vai

```text
Ludzu izveido ClickUp uzdevumu par jauno cenu lapu, prioritati augsta.
```

### Struktureta forma

```text
/task Nosaukums | Apraksts | steidzami
```

### Balss zinas

Ja ielikts `OPENAI_API_KEY`, vari sutit ari balss zinu. Bots:

1. Lejupielades audio no Telegram.
2. Parveidos to tekstaa.
3. Meginas saprast nosaukumu, aprakstu un prioritati.
4. Izveidos uzdevumu tai pasai ClickUp listei.

## Prioritates

Bots mekle prioritati no dabiskas valodas. Atbalstiti, piemeram:

- `steidzami`, `steidzams`, `urgent`, `asap`, `critical`
- `augsta`, `high`
- `normala`, `normal`, `medium`
- `zema`, `low`
- `priority 1`, `priority 2`, `priority 3`, `priority 4`

Ja prioritati nevar noteikt, tiek lietota `3` jeb normala.

## Kur vins liks uzdevumu

Bots neizvelas starp vairakam listem. Visi uzdevumi vienmer tiek veidoti viena ClickUp liste:

```text
https://api.clickup.com/api/v2/list/{CLICKUP_LIST_ID}/task
```

Tas nozime, ka pietiek pareizi atrast un ielikt savu `CLICKUP_LIST_ID`.

## Automatisks assignee

Ja gribi, lai visi jaunie uzdevumi automatiski tiek piekirsti vienam cilvekam,
pieliec Vercel vide:

```text
CLICKUP_ASSIGNEE_ID=12345678
```

Svarigi: ClickUp API izmanto lietotaja ID, nevis e-pastu.
