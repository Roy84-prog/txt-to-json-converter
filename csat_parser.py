import re
import json


class CSATParser:
    def __init__(self, markdown_text):
        self.md = markdown_text

    def extract_block(self, tag_name):
        pattern = f"<{tag_name}>(.*?)</{tag_name}>"
        match = re.search(pattern, self.md, re.DOTALL)
        return match.group(1).strip() if match else ""

    def search_line(self, pattern, text):
        match = re.search(pattern, text)
        return match.group(1).strip() if match else ""

    def search_block(self, pattern, text):
        match = re.search(pattern, text, re.DOTALL)
        return match.group(1).strip() if match else ""

    def parse_option_analysis(self):
        step3 = self.extract_block("STEP_3_OPTION_ANALYSIS")
        lines = [line.strip() for line in step3.split('\n') if line.strip() and '|' in line]

        options_analysis = []
        for line in lines:
            parts = [p.strip() for p in line.split('|')]
            choice_clean, trans_clean, error_type, reason = "", "", "", ""

            if len(parts) >= 4:
                choice_clean = re.sub(r"^([①-⑤])\s*:\s*", r"\1 ", parts[0]).strip()
                trans_clean = parts[1]
                error_type = parts[2]
                reason = parts[3]
            elif len(parts) == 3:
                raw_front = re.sub(r"^([①-⑤])\s*:\s*", r"\1 ", parts[0])
                front_parts = raw_front.split(':', 1)
                choice_clean = front_parts[0].strip()
                trans_clean = front_parts[1].strip() if len(front_parts) > 1 else ""
                error_type = parts[1]
                reason = parts[2]
            else:
                continue

            opt_dict = {
                "choice": choice_clean,
                "trans": trans_clean,
                "error_type": error_type
            }

            if "정답" in error_type:
                opt_dict["correct_reason"] = reason
            else:
                opt_dict["reason"] = reason
            options_analysis.append(opt_dict)

        return options_analysis

    def parse_visual_text(self, sub_question):
        step7 = self.extract_block("STEP_7_VISUAL_TEXT")

        passage = self.search_block(r"<PASSAGE>\s*(.*?)\s*</PASSAGE>", step7)
        options_text = self.search_block(r"<OPTIONS>\s*(.*?)\s*</OPTIONS>", step7)

        if not passage and not options_text:
            passage = step7

        footnotes = []
        if passage:
            passage_lines = passage.split('\n')
            clean_passage_lines = []

            for line in passage_lines:
                line_stripped = line.strip()
                if re.match(r"^\*+\s*\S+", line_stripped):
                    footnotes.append(line_stripped)
                else:
                    clean_passage_lines.append(line)

            passage = " ".join(clean_passage_lines)
            passage = passage.replace('\\n', ' ').replace('\n', ' ')
            passage = re.sub(r'\s+', ' ', passage).strip()

        visual_options = []
        if options_text:
            raw_options = [line.strip() for line in options_text.split('\n') if line.strip()]
            for opt in raw_options:
                opt_clean = opt.replace('\\n', ' ').replace('\n', ' ')
                opt_clean = re.sub(r'\s+', ' ', opt_clean).strip()
                visual_options.append(opt_clean)

        options_visual = [{"sub_question": sub_question, "options": visual_options}]

        return passage, options_visual, footnotes

    def parse_sentence_analysis(self):
        step8 = self.extract_block("STEP_8_SENTENCE_ANALYSIS")
        blocks = re.findall(r"<SENTENCE_BLOCK>(.*?)</SENTENCE_BLOCK>", step8, re.DOTALL)

        analysis_list = []
        for block in blocks:
            item = {}
            for key in ["Num", "Eng", "Kor", "Lib", "Easy", "Mark", "Context", "Tip"]:
                match = re.search(rf"{key}:\s*(.*?)(?=\n[A-Z][a-z]+:|$)", block, re.DOTALL)
                if match:
                    val = match.group(1).strip()

                    if key in ["Eng", "Kor", "Lib"]:
                        val = re.sub(r'[①②③④⑤]\s*', '', val)
                        val = re.sub(r'^\s*\([A-C]\)\s*', '', val)
                        val = re.sub(r'^([❶❷❸❹❺❻❼❽❾❿⓫⓬⓭⓮⓯⓰⓱⓲⓳⓴])\s*\([A-C]\)\s*', r'\1 ', val)

                    if key == "Num":
                        item["num"] = int(val)
                    elif key == "Eng":
                        item["eng_analyzed"] = val
                    elif key == "Kor":
                        item["kor_translation"] = val
                    elif key == "Lib":
                        item["kor_liberal_translation"] = val
                    elif key == "Easy":
                        item["easy_exp"] = val
                    elif key == "Mark":
                        item["summary_mark"] = val
                    elif key == "Context":
                        item["context_meaning"] = val
                    elif key == "Tip":
                        tips = []
                        for t_line in [l.strip() for l in val.split('\n') if l.strip()]:
                            t_match = re.search(r"\[(.*?)\]\s*\"(.*?)\"\s*:\s*(.*)", t_line)
                            if t_match:
                                tips.append({
                                    "tag": f"[{t_match.group(1).strip()}]",
                                    "target": t_match.group(2).strip(),
                                    "explanation": t_match.group(3).strip()
                                })
                        item["syntax_tip"] = tips
            if item:
                analysis_list.append(item)
        return analysis_list

    def parse_learning_point(self):
        step12 = self.extract_block("STEP_12_LEARNING_POINT")
        logic_match = self.search_block(r"\[독해 \(Logic\)\]\s*(.*?)(?=\[구문 \(Grammar\)\]|$)", step12)
        grammar_match = self.search_block(r"\[구문 \(Grammar\)\]\s*(.*)", step12)

        def extract_bullets(text):
            if not text:
                return []
            lines = []
            for line in text.split('\n'):
                line = line.strip()
                if line.startswith('*'):
                    clean_line = re.sub(r"^\*\s*", "", line)
                    clean_line = re.sub(r" (흐름 파악|이해|주의|파악|확인)\.$", r" **\1**.", clean_line)
                    lines.append(clean_line)
            return lines

        return {
            "logic": extract_bullets(logic_match),
            "grammar": extract_bullets(grammar_match)
        }

    def parse_predicted_data(self):
        step13 = self.extract_block("STEP_13_PREDICTED_DATA")
        items = [i.strip() for i in step13.split('||') if i.strip()]

        type_mapping = {"빈칸 추론": "blank_inference", "함축 의미": "implied_meaning", "어법 대비": "grammar_correction"}
        predicted_list = []

        for item in items:
            parts = {}
            for p in item.split('|'):
                if ':' in p:
                    k, v = p.split(':', 1)
                    parts[k.strip().lower()] = v.strip()

            if "type" not in parts:
                continue

            raw_type = parts["type"]
            mapped_type = next((eng for kor, eng in type_mapping.items() if kor in raw_type), "unknown")

            reason_val, trans_val = "", ""
            for k, v in parts.items():
                if "reason" in k:
                    reason_val = v
                if "trans" in k:
                    trans_val = v

            sent_no_str = re.sub(r"[^\d]", "", parts.get("sentence_no", "0"))

            data = {
                "type": mapped_type,
                "sentence_no": int(sent_no_str) if sent_no_str else 0,
                "target": parts.get("target", ""),
                "reason": reason_val
            }

            if mapped_type == "blank_inference":
                data["paraphrase"] = parts.get("paraphrase", "")
                data["paraphrase_trans"] = trans_val
            elif mapped_type == "implied_meaning":
                data["meaning"] = parts.get("meaning", "")
                data["meaning_trans"] = trans_val
            elif mapped_type == "grammar_correction":
                data["distractor"] = parts.get("distractor", "")

            predicted_list.append(data)

        return predicted_list

    def to_dict(self):
        step1 = self.extract_block("STEP_1_SUMMARY")
        step2 = self.extract_block("STEP_2_ANSWER")
        step6 = self.extract_block("STEP_6_CLUES_DATA")
        step10 = self.extract_block("STEP_10_3STAGE")
        step11 = self.extract_block("STEP_11_SCENARIO")

        q_header = self.search_line(r"문두:\s*(.*)", step2)
        q_type = self.search_line(r"유형:\s*(.*)", step2)

        options_analysis = self.parse_option_analysis()
        passage_visual, options_visual, footnotes = self.parse_visual_text(q_header)

        if q_type in ["5", "7"] and options_visual:
            options_visual[0]["options"] = ["①", "②", "③", "④", "⑤"]

        key_sentences = []
        for item in self.extract_block("STEP_4_KEY_SENTENCES").split('||'):
            if item.strip():
                parts = {k.strip().lower(): v.strip() for k, v in
                         (p.split(':', 1) for p in item.split('|') if ':' in p)}
                key_sentences.append({
                    "type": parts.get("type", ""),
                    "sentence": parts.get("sentence", ""),
                    "translation": parts.get("trans", ""),
                    "reason": parts.get("reason", "")
                })

        vocab_list = []
        for item in self.extract_block("STEP_5_VOCAB").split('||'):
            if item.strip():
                parts = {k.strip().lower(): v.strip() for k, v in
                         (p.split(':', 1) for p in item.split('|') if ':' in p)}

                etym_val = parts.get("etym", "")
                if not etym_val:
                    etym_val = parts.get("etymology", "")

                vocab_list.append({
                    "word": parts.get("word", ""),
                    "pronunciation": parts.get("pron", ""),
                    "meaning": parts.get("meaning", ""),
                    "synonym": parts.get("syn", ""),
                    "antonym": parts.get("ant", ""),
                    "confusing": parts.get("conf", ""),
                    "etymology": etym_val,
                    "chunk_example": parts.get("chunk", ""),
                    "chunk_translation": parts.get("chunktrans", "")
                })

        stage_matches = re.findall(r"<STAGE\s+range=[\"'](.*?)[\"']\s*>(.*?)</STAGE>", step10, re.DOTALL)
        three_stage_flow = []
        for range_val, inner_text in stage_matches:
            three_stage_flow.append({
                "range": range_val.strip(),
                "title": self.search_line(r"Title:\s*(.*)", inner_text),
                "content": self.search_line(r"Content:\s*(.*)", inner_text)
            })

        return {
            "meta_info": {
                "question_header": q_header,
                "source_origin": self.search_line(r"출처:\s*(.*)", step2),
                "question_type": q_type,
                "difficulty_level": self.search_line(r"difficulty_level\s*:\s*(.*)",
                                                     self.extract_block("STEP_14_difficulty_level"))
            },
            "visual_data": {
                "question_text_visual": passage_visual,
                "options_visual": options_visual,
                "footnotes": footnotes
            },
            "topic_data": {
                "keywords": self.search_line(r"소재:\s*(.*)", step1),
                "keywords_en": self.search_line(r"소재_EN:\s*(.*)", step1),
                "summary": self.search_line(r"요약:\s*(.*)", step1),
                "summary_en": self.search_line(r"요약_EN:\s*(.*)", step1),
                "csat_summary_problem": {
                    "summary_text": self.search_block(r"\[요약문\]\s*(.*?)(?=\[정답\])", step1),
                    "answer": self.search_block(r"\[정답\]\s*(.*?)(?=\[해석\])", step1),
                    "translation": self.search_block(r"\[해석\]\s*(.*)", step1)
                }
            },
            "answer_data": {
                "correct_choice": self.search_line(r"정답:\s*(.*)", step2),
                "explanation_summary": self.search_block(r"해설요약:\s*(.*?)(?=근거_단서:)", step2),
                "clues": {
                    "material": self.search_line(r"소재 및 방향성:\s*(.*)", step2),
                    "keywords_list": [k.strip() for k in
                                      self.search_line(r"Subject_Keywords:\s*(.*)", step6).split(',')],
                    "target_sentences": [s.strip() for s in
                                         self.search_block(r"단서:\s*(.*?)(?=\n근거_논리:)", step2).split('\n') if
                                         s.strip()],
                    "logic_flow": self.search_line(r"근거_논리:\s*(.*)", step2)
                }
            },
            "options_analysis": options_analysis,
            "key_sentences": key_sentences,
            "vocab_list": vocab_list,
            "sentence_analysis": self.parse_sentence_analysis(),
            "logic_map": [line.strip() for line in self.extract_block("STEP_9_LOGIC_MAP").split('\n') if line.strip()],
            "three_stage_flow": three_stage_flow,
            "class_scenario": {
                "simulation_text": self.search_block(r"Simulation:\s*(.*?)(?=\nGuide:)", step11),
                "guide_ment": self.search_block(r"Guide:\s*(.*?)(?=\nTip:)", step11),
                "tip_ment": self.search_block(r"Tip:\s*(.*)", step11)
            },
            "learning_point": self.parse_learning_point(),
            "predicted_exam_data": self.parse_predicted_data()
        }
