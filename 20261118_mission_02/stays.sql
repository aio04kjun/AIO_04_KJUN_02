CREATE TABLE stays (
    city TEXT NOT NULL,
    name TEXT NOT NULL,
    area TEXT NOT NULL,
    price INTEGER NOT NULL,
    sheltered INTEGER NOT NULL,
    image_index INTEGER NOT NULL,
    description TEXT NOT NULL
);

INSERT INTO stays VALUES
    ('강릉', '경포 파도 스테이', '경포', 128000, 1, 0, '큰 창이 있는 객실에서 바다를 보며 느긋하게 쉴 수 있어요.'),
    ('강릉', '경포 해안 스테이', '경포', 98000, 0, 1, '날이 좋을 때 경포해변 산책을 시작하기 좋은 숙소예요.'),
    ('태안', '태안 솔바람 캐빈', '해안', 96000, 0, 2, '소나무 사이에 자리해 해변과 숲을 함께 둘러보기 좋아요.'),
    ('태안', '태안 갯빛 스테이', '해안', 118000, 1, 3, '큰 창이 있는 라운지에서 날씨에 구애받지 않고 쉬기 좋아요.'),
    ('여수', '여수 섬빛 스테이', '엑스포·오동도', 138000, 1, 4, '실내에서 섬이 이어지는 바다 풍경을 감상하기 좋아요.'),
    ('여수', '여수 항구 스테이', '엑스포·오동도', 89000, 0, 5, '항구 근처에서 바닷바람을 느끼며 여유롭게 걷기 좋아요.');
