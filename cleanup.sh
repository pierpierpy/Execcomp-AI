#!/bin/bash
# bash /home/pdipasquale/MIIA/stuff/cleanup.sh
set -e

OUTPUT_DIR="/home/pdipasquale/MIIA/stuff/output"
PATTERNS=("*_origin.pdf" "*_layout.pdf")
DRY_RUN=false

if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "=== DRY RUN - nessun file verrà eliminato ==="
fi

echo "Cercando file da eliminare in $OUTPUT_DIR..."

# Conta file per ogni pattern
total=0
for pattern in "${PATTERNS[@]}"; do
    count=$(find "$OUTPUT_DIR" -type f -name "$pattern" 2>/dev/null | wc -l)
    echo "  $pattern: $count file"
    total=$((total + count))
done

if [[ $total -eq 0 ]]; then
    echo "Nessun file da eliminare!"
    exit 0
fi

echo ""
echo "Totale: $total file da eliminare"

if $DRY_RUN; then
    echo ""
    echo "Per eliminare davvero, esegui: ./cleanup.sh"
    exit 0
fi

echo ""
read -p "Procedere con l'eliminazione? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Annullato."
    exit 1
fi

echo ""
echo "Eliminazione in corso..."

# Elimina con progresso usando parallel se disponibile, altrimenti xargs
deleted=0
for pattern in "${PATTERNS[@]}"; do
    echo "Eliminando $pattern..."
    
    # Conta file per questo pattern
    pattern_count=$(find "$OUTPUT_DIR" -type f -name "$pattern" 2>/dev/null | wc -l)
    
    if [[ $pattern_count -gt 0 ]]; then
        # Usa xargs con parallelismo e mostra progresso
        find "$OUTPUT_DIR" -type f -name "$pattern" 2>/dev/null | \
            xargs -P 8 -I {} sh -c 'rm -f "$1" && echo -ne "\r  Eliminati: $((++i))/$2"' _ {} "$pattern_count" 2>/dev/null &
        
        # Mostra progresso in tempo reale
        while jobs %1 &>/dev/null 2>&1; do
            remaining=$(find "$OUTPUT_DIR" -type f -name "$pattern" 2>/dev/null | wc -l)
            done_count=$((pattern_count - remaining))
            pct=$((done_count * 100 / pattern_count))
            printf "\r  [%-50s] %d%% (%d/%d)" $(printf '#%.0s' $(seq 1 $((pct/2)))) $pct $done_count $pattern_count
            sleep 1
        done
        wait
        
        echo ""
        deleted=$((deleted + pattern_count))
    fi
done

echo ""
echo "✓ Completato! Eliminati $deleted file."

# Mostra spazio recuperato
echo ""
echo "Spazio attuale output:"
du -sh "$OUTPUT_DIR" 2>/dev/null || echo "(calcolo in corso...)"
