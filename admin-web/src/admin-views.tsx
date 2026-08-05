import React, { FormEvent, useMemo, useState } from "react";
import { api, confirmAction } from "./api";
import type { BroadcastItem } from "./types";
import { Badge, ErrorBox, Field, Header, Icon, Loading, date, useData, useToast } from "./admin-ui";

type RetryPreview = {
  requested: number;
  found: number;
  eligible_broadcasts: number;
  retriable_recipients: number;
  missing: number;
  items: Array<{ id: string; recipients: number }>;
};

type RetryModal = { key: string; preview: RetryPreview } | null;

function idempotencyKey() {
  return `broadcast-retry:${Date.now()}:${crypto.randomUUID()}`;
}

export function BroadcastsView() {
  const [status, setStatus] = useState("all");
  const state = useData(() => api<BroadcastItem[]>("/broadcasts?limit=300"), []);
  const [created, setCreated] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [retryModal, setRetryModal] = useState<RetryModal>(null);
  const [busy, setBusy] = useState(false);
  const { push } = useToast();
  const items = useMemo(
    () => (state.data || []).filter((item) => status === "all" || item.status === status),
    [state.data, status],
  );

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    try {
      const item = await api<{ id: string }>("/broadcasts", {
        method: "POST",
        body: JSON.stringify({
          audience_type: form.get("audience_type"),
          title_id: form.get("title_id") || null,
          text: form.get("text"),
          button_text: form.get("button_text") || null,
          button_url: form.get("button_url") || null,
          scheduled_at: form.get("scheduled_at") ? new Date(String(form.get("scheduled_at"))).toISOString() : null,
          send_now: form.get("send_now") === "on",
          selected_user_ids: [],
        }),
      });
      setCreated(item.id);
      event.currentTarget.reset();
      await state.reload();
      push(`Ğ Ğ°ÑÑÑ‹Ğ»ĞºĞ° ÑĞ¾Ğ·Ğ´Ğ°Ğ½Ğ°: ${item.id}`, "success");
    } catch (cause) {
      push(cause instanceof Error ? cause.message : String(cause), "error");
    } finally {
      setBusy(false);
    }
  }

  async function photo(file: File) {
    if (!created) {
      push("Ğ¡Ğ½Ğ°Ñ‡Ğ°Ğ»Ğ° ÑĞ¾Ğ·Ğ´Ğ°Ğ¹Ñ‚Ğµ Ñ€Ğ°ÑÑÑ‹BëF¸ˆ°€‰•ÉÉ½Èˆ¤ì(€€€€€É•ÑÕÉ¸ì(€€€ô(€€€½¹ÍĞ‰½‘ä€ô¹•Ü½Éµ…Ñ„ ¤ì(€€€‰½‘ä¹Í•Ğ ‰™¥±”ˆ°™¥±”¤ì(€€€ÑÉäì(€€€€€…İ…¥Ğ…Á¤¡€½‰É½…‘…ÍÑÌ¼‘íÉ•…Ñ•‘ô½Á¡½Ñ½€°ìµ•Ñ¡½è€‰A=MPˆ°‰½‘äô¤ì(€€€€€ÁÕÍ  ‹B“BûFBøƒBÿFBãBëFB×BÿBïB×B÷Bø¸ˆ°€‰ÍÕ•ÍÌˆ¤ì(€€€ô…Ñ €¡…ÕÍ”¤ì(€€€€€ÁÕÍ ¡…ÕÍ”¥¹ÍÑ…¹•½˜ÉÉ½È€ü…ÕÍ”¹µ•ÍÍ…”€èMÑÉ¥¹œ¡…ÕÍ”¤°€‰•ÉÉ½Èˆ¤ì(€€€ô(€ô((€…Íå¹Œ™Õ¹Ñ¥½¸ÁÉ•Ù¥•İI•ÑÉä ¤ì(€€€¥˜€ …Í•±•Ñ•¹±•¹Ñ ¤É•ÑÕÉ¸ì(€€€½¹ÍĞ­•ä€ô¥‘•µÁ½Ñ•¹å-•ä ¤ì(€€€Í•Ñ	ÕÍä¡ÑÉÕ”¤ì(€€€ÑÉäì(€€€€€½¹ÍĞÁÉ•Ù¥•Ü€ô…İ…¥Ğ…Á¤ñI•ÑÉåAÉ•Ù¥•Üø ˆ½‰É½…‘…ÍÑÌ½É•ÑÉäµ™…¥±•ˆ°ì(€€€€€€€µ•Ñ¡½è€‰A=MPˆ°(€€€€€€€‰½‘äè)M=8¹ÍÑÉ¥¹¥™ä¡ì‰É½…‘…ÍÑ}¥‘ÌèÍ•±•Ñ•°‘Éå}ÉÕ¸èÑÉÕ”°¥‘•µÁ½Ñ•¹å}­•äè­•äô¤°(€€€€€ô¤ì(€€€€€Í•ÑI•ÑÉå5½‘…°¡ì­•ä°ÁÉ•Ù¥•Üô¤ì(€€€ô…Ñ €¡…ÕÍ”¤ì(€€€€€ÁÕÍ ¡…ÕÍ”¥¹ÍÑ…¹•½˜ÉÉ½È€ü…ÕÍ”¹µ•ÍÍ…”€èMÑÉ¥¹œ¡…ÕÍ”¤°€‰•ÉÉ½Èˆ¤ì(€€€ô™¥¹…±±äì(€€€€€Í•Ñ	ÕÍä¡™…±Í”¤ì(€€€ô(€ô((€…Íå¹Œ™Õ¹Ñ¥½¸•á•ÕÑ•I•ÑÉä ¤ì(€€€¥˜€ …É•ÑÉå5½‘…°¤É•ÑÕÉ¸ì(€€€½¹ÍĞ…•ÁÑ•€ô…İ…¥Ğ½¹™¥ÉµÑ¥½¸ (€€€€€ƒBKB×FB÷FFF0ƒBÈƒBûFB×FB×BÓF0€‘íÉ•ÑÉå5½‘…°¹ÁÉ•Ù¥•Ü¹•±¥¥‰±•}‰É½…‘…ÍÑÍôƒFBÃFFF/BïBûBèƒBà€‘íÉ•ÑÉå5½‘…°¹ÁÉ•Ù¥•Ü¹É•ÑÉ¥…‰±•}É•¥Á¥•¹ÑÍôƒBÿBûBïFFBÃFB×BïB×Bäı€°(€€€€¤ì(€€€¥˜€ ……•ÁÑ•¤É•ÑÕÉ¸ì(€€€Í•Ñ	ÕÍä¡ÑÉÕ”¤ì(€€€ÑÉäì(€€€€€½¹ÍĞÉ•ÍÕ±Ğ€ô…İ…¥Ğ…Á¤ñI•ÑÉåAÉ•Ù¥•Ü€˜ìÉ•Á±…å•è‰½½±•…¸ôø ˆ½‰É½…‘…ÍÑÌ½É•ÑÉäµ™…¥±•ˆ°ì(€€€€€€€µ•Ñ¡½è€‰A=MPˆ°(€€€€€€€‰½‘äè)M=8¹ÍÑÉ¥¹¥™ä¡ì(€€€€€€€€€‰É½…‘…ÍÑ}¥‘ÌèÍ•±•Ñ•°(€€€€€€€€€‘Éå}ÉÕ¸è™…±Í”°(€€€€€€€€€¥‘•µÁ½Ñ•¹å}­•äèÉ•ÑÉå5½‘…°¹­•ä°(€€€€€€€ô¤°(€€€€€ô¤ì(€€€€€Í•ÑI•ÑÉå5½‘…°¡¹Õ±°¤ì(€€€€€Í•ÑM•±•Ñ•¡mt¤ì(€€€€€…İ…¥ĞÍÑ…Ñ”¹É•±½… ¤ì(€€€€€ÁÕÍ  (€€€€€€€É•ÍÕ±Ğ¹É•Á±…å•(€€€€€€€€€€ü€‹B{BÿB×FBÃFBãF<ƒFBÛBÔƒBËF/BÿBûBïB÷F?BïBÃFF0ìƒBËBûBßBËFBÃF'FGBôƒFBûFFBÃB÷FGB÷B÷F/BäƒFB×BßFBïF3FBÃF¸ˆ(€€€€€€€€€€èƒBHƒBûFB×FB×BÓF0ƒBËBûBßBËFBÃF'B×B÷BøƒFBÃFFF/BïBûBèè€‘íÉ•ÍÕ±Ğ¹•±¥¥‰±•}‰É½…‘…ÍÑÍô¹€°(€€€€€€€€‰ÍÕ•ÍÌˆ°(€€€€€€¤ì(€€€ô…Ñ €¡…ÕÍ”¤ì(€€€€€ÁÕÍ ¡…ÕÍ”¥¹ÍÑ…¹•½˜ÉÉ½È€ü…ÕÍ”¹µ•ÍÍ…”€èMÑÉ¥¹œ¡…ÕÍ”¤°€‰•ÉÉ½Èˆ¤ì(€€€ô™¥¹…±±äì(€€€€€Í•Ñ	ÕÍä¡™…±Í”¤ì(€€€ô(€ô((€É•ÑÕÉ¸€ñÍ•Ñ¥½¸±…ÍÍ9…µ”ô‰Á…”‰É½…‘…ÍÑÌµİ½É­‰•¹ ˆø(€€€€ñ!•…‘•È(€€€€€Ñ¥Ñ±”ô‹BƒFFB÷F/BÔƒFBÃFFF/BïBëBàˆ(€€€€€‘•ÍÉ¥ÁÑ¥½¸ô‹B‹B×BëFF°ƒFBûFBø°ƒBëB÷BûBÿBëBÀ°ƒFBÃFBÿBãFBÃB÷BãBÔƒBàƒBÇB×BßBûBÿBÃFB÷BûBÔƒBËBûFFFBÃB÷BûBËBïB×B÷BãBÔ™…¥±•·BÿBûBïFFBÃFB×BïB×Bä¸ˆ(€€€€€…Ñ¥½¸õìñ‰ÕÑÑ½¸±…ÍÍ9…µ”ô‰İ¥Ñ µ¥½¸ˆ½¹±¥¬õíÍÑ…Ñ”¹É•±½…‘ôøñ%½¸¹…µ”ô‰É•™É•Í ˆ¼ûB{BÇB÷BûBËBãFF0ğ½‰ÕÑÑ½¸ùô(€€€€¼ø(€€€íÍÑ…Ñ”¹•ÉÉ½È€˜˜€ñÉÉ½É	½àÑ•áĞõíÍÑ…Ñ”¹•ÉÉ½Éô¼ùô€(€€€€ñ‘¥Ø±…ÍÍ9…µ”ô‰½±Õµ¹Ì‰É½…‘…ÍÑÌµ±…å½ÕĞˆø(€€€€€€ñ™½É´±…ÍÍ9…µ”ô‰Á…¹•°™½É´‰É½…‘…ÍĞµÉ•…Ñ”ˆ½¹MÕ‰µ¥ĞõíÉ•…Ñ•ô…É¥„µ±…‰•°ô‹BwBûBËBÃF<ƒFBÃFFF-½­#à¢Æƒ3í	İí-ò½½­Âöƒ3à¢Äf–VÆBÆ&VÃÒ-	M-íò#ãÇ6VÆV7BæÖSÒ&VF–Væ6U÷G—R#ãÆ÷F–öâfÇVSÒ&ÆÂ#í	-SÂö÷F–öããÆ÷F–öâfÇVSÒ&7F—fU÷f—#í	­--İ½Rd•Âö÷F–öããÆ÷F–öâfÇVSÒ'f—öw&6R#åd•²w&6SÂö÷F–öããÆ÷F–öâfÇVSÒ'7FæF&B#å7FæF&CÂö÷F–öããÆ÷F–öâfÇVSÒ'F—FÆUöföÆÆ÷vW'2#í	ıíMı}­‚--½Âö÷F–öããÂ÷6VÆV7CãÂôf–VÆCà¢Äf–VÆBÆ&VÃÒ%UT”B--½#ãÆ–çWBæÖSÒ'F—FÆUö–B"Æ6V†öÆFW#Ò-
-í½Í­âM½òıíMı}­í"--½"óãÂôf–VÆCà¢Äf–VÆBÆ&VÃÒ-
-]­"#ãÇFW‡F&VæÖSÒ'FW‡B"&÷w3×³wÒÖ„ÆVæwFƒ×³#GÒ&WV—&VBóãÂôf–VÆCà¢ÆF—b6Æ74æÖSÒ'&÷r#ãÄf–VÆBÆ&VÃÒ-
-]­"­İíı­‚#ãÆ–çWBæÖSÒ&'WGFöå÷FW‡B"Ö„ÆVæwFƒ×³cGÒóãÂôf–VÆCãÄf–VÆBÆ&VÃÒ%U$Â#ãÆ–çWBæÖSÒ&'WGFöå÷W&Â"G—SÒ'W&Â"óãÂôf–VÆCãÂöF—cà¢Äf–VÆBÆ&VÃÒ-	M-í-ı-­‚#ãÆ–çWBæÖSÒ'66†VGVÆVEöB"G—SÒ&FFWF–ÖRÖÆö6Â"óãÂôf–VÆCà¢ÆÆ&VÂ6Æ74æÖSÒ&6†V6¶&÷‚#ãÆ–çWBæÖSÒ'6VæEöæ÷r"G—SÒ&6†V6¶&÷‚"óâ	í-ı--Â}3ÂöÆ&VÃà¢Æ'WGFöâ6Æ74æÖSÒ'&–Ö'’"F—6&ÆVC×¶'W7—Óç¶'W7’ò-
í]İı]Î(
b"¢-
í}M-Â'ÓÂö'WGFöãà¢ÆÆ&VÂ6Æ74æÖS×¶WÆöBG¶7&VFVBò""¢"F—6&ÆVF'ÖÓí
Mí-â¢í}Mİİí’½½­SÆ–çWBF—6&ÆVC×²7&VFVGÒ†–FFVâG—SÒ&f–ÆR"66WCÒ&–ÖvRò¢"öä6†ævS×²†WfVçC¢&V7Bä6†ævTWfVçCÄ…DÔÄ–çWDVÆVÖVçCâ’ÓâWfVçBçF&vWBæf–ÆW3òå³Òbb†÷Fò†WfVçBçF&vWBæf–ÆW5³Ò—ÒóãÂöÆ&VÃà¢¶7&VFVBbbÇ6ÖÆÂ6Æ74æÖSÒ&'&öF67BÖ7&VFVB#í
-]­=ò´.ô.´,ˆÛÙOØÜ™X]YOØÛÙOÜÛX[ŸBˆÙ›Ü›O‚ˆ]ˆÛ\ÜÓ˜[YOHœ[™[œ›ØYØ\İ[\İ\[™[‚ˆ]ˆÛ\ÜÓ˜[YOH˜œ›ØYØ\İ[\İZXY‚ˆ]Ï´'ô/´`t.ô-t-4/t.4-H4`4,4`t`tbĞ»ĞºĞ¸</h3><p>Failed-Ğ·Ğ°Ğ¿Ğ¸ÑĞ¸ Ğ¼Ğ¾Ğ¶Ğ½Ğ¾ Ğ²Ñ‹Ğ±Ñ€Ğ°Ñ‚ÑŒ Ğ¸ Ğ²ĞµÑ€Ğ½ÑƒÑ‚ÑŒ Ğ² Ğ¾Ñ‡ĞµÑ€ĞµĞ´ÑŒ Ñ‚Ğ¾Ğ»ÑŒĞºĞ¾ Ğ¿Ğ¾ÑĞ»Ğµ dry-run.</p></div>
          <div><select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Ğ¤Ğ¸Ğ»ÑŒÑ‚Ñ† Ğ¿Ğ¾ ÑÑ‚Ğ°Ñ‚ÑƒÑÑƒ"><option value="all">Ğ’ÑĞµ ÑÑ‚Ğ°Ñ‚ÑƒÑÑ‹</option><option value="draft">Ğ§ĞµÑ€Ğ½Ğ¾Ğ²Ğ¸Ğº</option><option value="scheduled">Ğ—Ğ°Ğ¿Ğ»Ğ°Ğ½Ğ¸Ñ€Ğ¾Ğ²Ğ°Ğ½Ğ¾</option><option value="processing">Ğ’Ñ‹Ğ¿Ğ¾Ğ»Ğ½ÑĞµÑ‚ÑÑ</option><option value="completed">Ğ—Ğ°Ğ²ĞµÑ€ÑˆĞµĞ½Ğ¾</option><option value="failed">ĞÑˆĞ¸Ğ±ĞºĞ°</option><option value="cancelled">ĞÑ‚Ğ¼ĞµĞ½ĞµĞ½Ğ¾</option></select><button disabled={!selected.length || busy} onClick={previewRetry}>Dry-run retry ({selected.length})</button></div>
        </div>
        {state.loading ? <Loading label="Ğ—Ğ°Ğ³Ñ€ÑƒĞ¶Ğ°ĞµĞ¼ Ñ€Ğ°ÑÑÑ‹Ğ»ĞºĞ¸â€¦"/> : items.length ? <div className="cards compact broadcast-cards">{items.map((item) => <article key={item.id} className={selected.includes(item.id) ? "selected" : ""}>
          <label className="broadcast-select"><input type="checkbox" disabled={item.status !== "failed"} checked={selected.includes(item.id)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id))}/><span className="sr-only">Ğ’Ñ‹Ğ±Ñ€Ğ°Ñ‚ÑŒ failed-Ñ€Ğ°ÑÑÑ‹BïBëF¸ğ½ÍÁ…¸øğ½±…‰•°ø(€€€€€€€€€€ñ‘¥Ø±…ÍÍ9…µ”ô‰‰É½…‘…ÍĞµ…Éµµ…¥¸ˆøñ‘¥Ø±…ÍÍ9…µ”ô‰¥Ñ•´µ¡•…ˆøñÍÑÉ½¹œùí¥Ñ•´¹Ñ•áĞ¹Í±¥” À°€ÄĞÀ¥ôğ½ÍÑÉ½¹œøñ	…‘”Ù…±Õ”õí¥Ñ•´¹ÍÑ…ÑÕÍô¼øğ½‘¥ØøñÍµ…±°ùí¥Ñ•´¹Í•¹Ñ}½Õ¹Ñô½í¥Ñ•´¹Ñ½Ñ…±}½Õ¹Ñô°ƒBûF#BãBÇBûBèí¥Ñ•´¹™…¥±•‘}½Õ¹Ñô°ƒBÿFBûBÿFF'B×B÷Bøí¥Ñ•´¹Í­¥ÁÁ•‘}½Õ¹Ñôƒ
Üí‘…Ñ”¡¥Ñ•´¹É•…Ñ•‘}…Ğ¥ôğ½Íµ…±°øñ½‘”ùí¥Ñ•´¹¥‘ôğ½½‘”øğ½‘¥Øø(€€€€€€€€ğ½…ÉÑ¥±”ø¥ôğ½‘¥Øø€è€ñ‘¥Ø±…ÍÍ9…µ”ô‰•µÁÑäµÍÑ…Ñ”ˆøñ%½¸¹…µ”ô‰Í•¹ˆÍ¥é”õìÌÁô¼øñÍÑÉ½¹œûBƒBÃFFF-½í¢İRİM]ÓÂ÷7G&öæsãÇ7ãí	}Í]İ-RM½Í-½‚í}M-Rİí-=â½½­2ãÂ÷7ããÂöF—cçĞ¢ÂöF—cà¢ÂöF—cà¢·&WG'”ÖöFÂbbÆF—b6Æ74æÖSÒ&FÖ–âÖÖöFÂÖ&6¶G&÷"&öÆSÒ'&W6VçFF–öâ"öäÖ÷W6TF÷vã×²†WfVçB’ÓâWfVçBçF&vWBÓÓÒWfVçBæ7W'&VçEF&vWBbb6WE&WG'”ÖöFÂ†çVÆÂ—Óà¢Ç6V7F–öâ6Æ74æÖSÒ&FÖ–âÖÖöFÂ"&öÆSÒ&F–Æör"&–ÖÖöFÃÒ'G'VR"&–ÖÆ&VÆÆVF'“Ò'&WG'’×F—FÆR#à¢Æ†VFW#ãÆF—cãÆƒ"–CÒ'&WG'’×F—FÆR#äG'’×'VâÍí-í=â&WG'“Âöƒ#ãÇí	­İMM-²=M="ıí--íİâ}-İ²ıíBGf—6÷'’Æö6²ı]]B}ıÍâãÂ÷ãÂöF—cãÆ'WGFöâ&–ÖÆ&VÃÒ-	}­½-Â"öä6Æ–6³×²‚’Óâ6WE&WG'”ÖöFÂ†çVÆÂ—Óì9sÂö'WGFöããÂö†VFW#à¢ÆFÂ6Æ74æÖSÒ'&WG'’×7VÖÖ'’#ãÆF—cãÆGCí	}ıí]İãÂöGCãÆFCç·&WG'”ÖöFÂç&Wf–Wrç&WVW7FVGÓÂöFCãÂöF—cãÆF—cãÆGCí	İM]İâf–ÆVCÂöGCãÆFCç·&WG'”ÖöFÂç&Wf–Wræf÷VæGÓÂöFCãÂöF—cãÆF—cãÆGCí	Mí-=ıİâ´.ô/´.ÙÜ™]S[Ù[œ™]šY]Ë™[YÚX›WØœ›ØYØ\İßOÙÙ]]´'ô/´.ô`ôaô,4`´-t.ô-t.OÙÜ™]S[Ù[œ™]šY]Ëœ™]šXX›WÜ™XÚ\Y[ßOÙÙ]Ù‚ˆ]ˆÛ\ÜÓ˜[YOHœ™]KZ][\ÈÜ™]S[Ù[œ™]šY]Ëš][\Ë›X\

][JHOˆ]ˆÙ^O^Ú][KšYOÛÙOÚ][KšYOØÛÙOÜ[Ú][Kœ™XÚ\Y[ßH4/ô/´.ô`ôaô,4`´-t.ô-t.OÜÜ[Ù]Š_OÙ]‚ˆ›Ûİ\]ÛˆÛÛXÚÏ^Ê
HOˆÙ]™]S[Ù[
[
_O´'´`´/4-t/t,Ø]Û]ÛˆÛ\ÜÓ˜[YOHœš[X\Hˆ\ØX›Y^È\™]S[Ù[œ™]šY]Ë™[YÚX›WØœ›ØYØ\İÈ\Ş_HÛÛXÚÏ^Ù^Xİ]T™]_OØ\ŞHÈ´$´bô/ô/´.ô/tcô-t`´`tcø )ˆˆˆ´'ô/´-4`´,´-t`4-4.4`´c™]HŸOØ]ÛÙ›Ûİ\‚ˆÜÙXİ[Û‚ˆÙ]ŸBˆÜÙXİ[ÛÂŸB