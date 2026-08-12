package com.example;

import java.util.List;
import java.util.Random;

/**
 * TierDemoProcessor — exercises all three analysis tiers of the optimizer.
 *
 *  Tier 1 (Rule Engine)  : mergeSortedLists, computeMonteCarloPortfolio
 *  Tier 2 (CodeBERT SVM) : getAccountId, isEmpty
 *  Tier 3 (Claude)       : applyTierPricing, generateReferenceCode
 */
public class TierDemoProcessor {

    private final String accountId;
    private final List<String> items;

    public TierDemoProcessor(String accountId, List<String> items) {
        this.accountId = accountId;
        this.items     = items;
    }

    // -------------------------------------------------------------------------
    // TIER 1 — Rule Engine catches these via SLE'17 keyword signals
    // -------------------------------------------------------------------------

    /**
     * Merges two sorted integer arrays into a single sorted array.
     *
     * Why Tier 1: function name lowercased contains "merge" and "mergesort"
     * (substring), giving 2 signals on the merge_sort pattern at 0.86 confidence
     * (threshold 0.85). Rule engine → C, 52% energy saving.
     */
    public int[] mergeSortedLists(int[] a, int[] b) {
        int[] out = new int[a.length + b.length];
        int i = 0, j = 0, k = 0;
        while (i < a.length && j < b.length)
            out[k++] = (a[i] <= b[j]) ? a[i++] : b[j++];
        while (i < a.length) out[k++] = a[i++];
        while (j < b.length) out[k++] = b[j++];
        return out;
    }

    /**
     * Runs a Monte Carlo simulation over a portfolio of asset prices.
     *
     * Why Tier 1: body contains "simulation", "random", and "gaussian" —
     * 3 signals on the monte_carlo pattern at 0.90 confidence. Has loops so
     * the interop-overhead override does not apply.
     * Rule engine → C, 56% energy saving.
     */
    public double[] computeMonteCarloPortfolio(double[] prices, int numSimulations) {
        double[] results = new double[numSimulations];
        Random rng = new Random(42);
        for (int i = 0; i < numSimulations; i++) {
            double sim = 0;
            for (double p : prices) {
                double gaussian = rng.nextGaussian();
                sim += p * (1.0 + gaussian * 0.15);
            }
            results[i] = sim / prices.length;
        }
        return results;
    }

    // -------------------------------------------------------------------------
    // TIER 2 — CodeBERT SVM catches these (no keyword signals, trivial structure)
    // -------------------------------------------------------------------------

    /**
     * Returns the account identifier.
     *
     * Why Tier 2: no SLE'17 signals anywhere → Tier 1 miss.
     * Single-line getter — structurally identical to "getAccountNumber()" and
     * "getAge()" which are labelled "trivial" in the training set.
     * CodeBERT SVM → trivial → keep.
     */
    public String getAccountId() {
        return this.accountId;
    }

    /**
     * Returns true when the item list is empty.
     *
     * Why Tier 2: no SLE'17 signals → Tier 1 miss.
     * This exact pattern ("return items == null || items.isEmpty()") is a
     * labelled training example for the "trivial" category.
     * CodeBERT SVM → trivial → keep.
     */
    public boolean isEmpty() {
        return items == null || items.isEmpty();
    }

    // -------------------------------------------------------------------------
    // TIER 3 — Claude handles these (novel business logic, no SLE'17 match)
    // -------------------------------------------------------------------------

    /**
     * Applies a volume-tiered discount for a customer segment.
     *
     * Why Tier 3: "count" appears as a substring of "discount", giving 1 weak
     * signal (score 0.78, below the 0.85 threshold) → Tier 1 miss.
     * The switch/conditional pricing structure has no structural resemblance to
     * any SLE'17 benchmark → CodeBERT low confidence → Claude.
     */
    public double applyTierPricing(String customerTier, double unitPrice, int quantity) {
        double subtotal = unitPrice * quantity;
        double discount;
        switch (customerTier) {
            case "PLATINUM": discount = quantity >= 500 ? 0.25 : 0.15; break;
            case "GOLD":     discount = quantity >= 200 ? 0.15 : 0.08; break;
            case "SILVER":   discount = quantity >= 100 ? 0.08 : 0.03; break;
            default:         discount = 0.0;
        }
        return subtotal * (1.0 - discount);
    }

    /**
     * Generates a structured reference code for a business entity.
     *
     * Why Tier 3: "format" from String.format hits the string_formatting
     * pattern (base confidence 0.75), but score is 0.75 < 0.85 → Tier 1 miss.
     * Novel string-assembly logic with no SLE'17 structural pattern
     * → CodeBERT low confidence → Claude.
     */
    public String generateReferenceCode(String entityType, String region, int sequenceId) {
        String prefix     = entityType.substring(0, Math.min(3, entityType.length())).toUpperCase();
        String regionCode = region.replaceAll("[^A-Z0-9]", "").substring(0, Math.min(2, region.length()));
        return String.format("%s-%s-%08d", prefix, regionCode, sequenceId);
    }
}
