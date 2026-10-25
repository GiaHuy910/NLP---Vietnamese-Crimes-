
from server.src.ner_pipeline.baseline import RuleBasedNER, _tokens

ner = RuleBasedNER()

tests = [
    "Nguyễn Văn An bị bắt tại hiện trường.",
    "Công an thu giữ tang vật.",
    "Đối tượng bị bắt tại Hà Nội.",
    "Đối tượng chiếm đoạt 50 triệu đồng.",
    "Đối tượng bị khởi tố về tội trộm cắp tài sản.",
    "Nạn nhân bị lấy mất điện thoại iPhone.",
    "Công an thu giữ heroin tại hiện trường.",
]

for sentence in tests:
    print("\nCâu:", sentence)
    print("Tokens:", _tokens(sentence))
    print("Entities:", ner.predict(sentence))
