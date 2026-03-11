import jiwer
GROUND_TRUTH_FILE = "transcription_system/ground_truth_transcript.txt"

GENERATED_FILE = "transcription_system/transcription.txt" 

def evaluate_files():
    try:
        with open(GROUND_TRUTH_FILE, "r", encoding="utf-8") as f:
            ground_truth_text = f.read().strip()
    except FileNotFoundError:
        print(f"Không tìm thấy file {GROUND_TRUTH_FILE}")
        return

    try:
        with open(GENERATED_FILE, "r", encoding="utf-8") as f:
            generated_text = f.read().strip()
    except FileNotFoundError:
        print(f"Không tìm thấy file {GENERATED_FILE}")
        return

    if not ground_truth_text or not generated_text:
        print("Một trong hai file đang bị trống, không thể chấm điểm!")
        return

    transforms = jiwer.Compose([jiwer.ToLowerCase(), jiwer.RemovePunctuation()])
    
    gt_clean = transforms(ground_truth_text.replace('\n', ' '))
    gen_clean = transforms(generated_text.replace('\n', ' '))

    wer_score = jiwer.wer(gt_clean, gen_clean)
    alignment = jiwer.process_words(gt_clean, gen_clean)

    print("\n" + "="*80)
    print("BÁO CÁO ĐÁNH GIÁ TỪ FILE (WER EVALUATION)")
    print("="*80)
    
    print(jiwer.visualize_alignment(alignment))
    
    print("-" * 80)
    print(f"Word Error Rate (WER): {wer_score * 100:.2f}%")
    print("="*80)

if __name__ == "__main__":
    evaluate_files()