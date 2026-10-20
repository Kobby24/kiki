"""
Translates numerical amounts into a sequence of spoken word keys.
The keys correspond to the pre-baked Edge TTS audio files in ai/assets/en_digits/.
"""

def _number_to_sequence(n: int) -> list[str]:
    """Convert an integer up to 999,999,999 to a sequence of audio asset keys."""
    if n == 0:
        return ["0"]
        
    seq = []
    
    # Millions
    if n >= 1000000:
        millions = n // 1000000
        seq.extend(_number_to_sequence(millions))
        seq.append("million")
        n %= 1000000
        if n > 0 and n < 100:
            seq.append("and")
            
    # Thousands
    if n >= 1000:
        thousands = n // 1000
        seq.extend(_number_to_sequence(thousands))
        seq.append("thousand")
        n %= 1000
        if n > 0 and n < 100:
            seq.append("and")
            
    # Hundreds
    if n >= 100:
        hundreds = n // 100
        seq.append(str(hundreds))
        seq.append("hundred")
        n %= 100
        if n > 0:
            seq.append("and")
            
    # Tens and units
    if n > 0:
        if n <= 19:
            seq.append(str(n))
        else:
            tens = (n // 10) * 10
            units = n % 10
            seq.append(str(tens))
            if units > 0:
                seq.append(str(units))
                
    return seq


def amount_to_words(amount: float | None) -> list[str]:
    """
    Convert a float amount to a sequence of Ghanaian currency audio keys.
    e.g. 125.50 -> ["1", "hundred", "and", "20", "5", "cedis", "and", "50", "pesewas"]
    """
    if amount is None or amount == 0:
        return ["0", "cedis"]
        
    # Python floating point rounding fix (e.g. 125.50 -> 125 cedis, 50 pesewas)
    cedis = int(amount)
    pesewas = round((amount - cedis) * 100)
    
    seq = []
    
    if cedis > 0:
        seq.extend(_number_to_sequence(cedis))
        seq.append("cedis")
        
    if pesewas > 0:
        if cedis > 0:
            seq.append("and")
        seq.extend(_number_to_sequence(pesewas))
        seq.append("pesewas")
        
    return seq
